"""Per-agent Telegram bot poller.

Each community agent can have its OWN Telegram bot (configured via the
agent's ``botToken`` in its telegram config, with ``deploymentStatus`` of
``deployed``/``active``). This service polls each such bot independently and
replies as that agent using the agent's own LLM provider + knowledge — exactly
like the dashboard "Test Agent" flow, but over Telegram DMs.

The global ExamShield bot is unaffected; it keeps answering as EXAMSHIELD AI.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.error
import urllib.request

from .llm_providers import ProviderConfig
from .llm_providers import chat_completion as provider_chat_completion
from .rag import RAGConfig, search_agent_knowledge
from .settings import Settings
from .store import AgentStore, JsonObject
from .telegram import _clean_telegram_html, _extract_sender, _extract_text

logger = logging.getLogger(__name__)

_TG_API = "https://api.telegram.org/bot"


def _call_telegram(bot_token: str, method: str, payload: JsonObject, *, timeout: int = 20) -> JsonObject:
    url = f"{_TG_API}{bot_token}/{method}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(str(body.get("description") or f"Telegram {method} failed."))
    return body.get("result", {})


def _get_updates(bot_token: str, offset: int, *, timeout: int = 0) -> list[JsonObject]:
    return _call_telegram(
        bot_token,
        "getUpdates",
        {
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": ["message", "edited_message"],
        },
        timeout=max(timeout + 5, 15),
    )


def _markdown_to_telegram_html(value: str) -> str:
    """Convert the lightweight markdown the model emits into Telegram HTML."""
    text = str(value or "").strip()
    # Bold first so the surrounding asterisks don't get caught by the italic rule.
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)
    return _clean_telegram_html(text)


def generate_agent_reply(
    agent_store: AgentStore,
    settings: Settings,
    agent: JsonObject,
    question: str,
) -> tuple[str | None, str | None]:
    """Build an agent reply the same way the dashboard Test Agent does.

    Returns ``(reply_text, error)`` — exactly one is non-None.
    """
    import time as _time

    agent_id = str(agent.get("id") or "")
    llm_config = agent_store.get_llm_config(agent_id)
    if not llm_config:
        return None, "LLM not configured for this agent."

    rag_config = RAGConfig(
        supabase_url=settings.supabase_url or "",
        supabase_service_role_key=settings.supabase_service_role_key or "",
        embed_function_url=f"{settings.supabase_url}/functions/v1/embed" if settings.supabase_url else "",
    )

    context_chunks: list[JsonObject] = []
    if rag_config.supabase_url:
        try:
            context_chunks = search_agent_knowledge(question, agent_id, rag_config)
        except Exception as exc:  # noqa: BLE001 - keep the agent responsive on RAG failure
            logger.warning("Agent %s RAG search failed: %s", agent_id, exc)
    if not context_chunks:
        context_chunks = agent_store.search_knowledge_chunks(agent_id, question)

    system_prompt = str(agent.get("systemPrompt") or "You are a helpful assistant.")
    if context_chunks:
        context_text = "\n\n".join(str(c.get("content", "")) for c in context_chunks)
        system_prompt += f"\n\nUse the following knowledge to answer:\n\n{context_text}"

    style = str(agent.get("responseStyle", "balanced") or "balanced")
    if style == "short":
        system_prompt += "\n\nKeep responses concise (1-2 short paragraphs)."
    elif style == "detailed":
        system_prompt += "\n\nProvide detailed, comprehensive answers."

    if agent.get("citationMode") and context_chunks:
        system_prompt += "\n\nCite sources when referencing specific information."

    # Telegram-flavoured formatting so emphasis actually renders in the app.
    system_prompt += (
        "\n\nYou are replying inside Telegram. Use Telegram-compatible formatting: "
        "**bold** for key terms, *italic* for softer emphasis, `code` for identifiers. "
        "Be warm, concise, and human."
    )

    provider_config = ProviderConfig(
        provider=str(llm_config.get("provider", "openai")),
        api_key=str(llm_config.get("apiKeyEncrypted", "") or ""),
        model=str(llm_config.get("model", "gpt-4o")),
        endpoint_url=str(llm_config.get("endpointUrl", "") or ""),
        extra_headers=llm_config.get("extraHeaders", {}) or {},
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    start = _time.monotonic()
    try:
        result = provider_chat_completion(provider_config, messages, max_tokens=1024, timeout=20)
    except Exception as exc:  # noqa: BLE001
        return None, f"{provider_config.provider} request failed: {exc}"
    latency_ms = int((_time.monotonic() - start) * 1000)

    response_text = str(result.get("content", "") or "").strip()
    if result.get("error"):
        return None, f"{provider_config.provider} request failed: {result['error']}"
    if not response_text:
        return None, "The configured model returned an empty response."

    try:
        agent_store.log_conversation(
            agent_id=agent_id,
            user_message=question,
            agent_response=response_text,
            sources=[
                {"content": str(c.get("content", ""))[:200], "similarity": c.get("similarity", 0)}
                for c in context_chunks
            ],
            latency_ms=latency_ms,
        )
    except Exception as exc:  # noqa: BLE001 - logging must never break the reply
        logger.warning("Agent %s conversation logging failed: %s", agent_id, exc)

    return response_text, None


class AgentTelegramService:
    """Polls every deployed community agent's own Telegram bot and replies as that agent."""

    def __init__(
        self,
        agent_store: AgentStore,
        settings: Settings,
        *,
        idle_sleep: float = 2.0,
    ) -> None:
        self.agent_store = agent_store
        self.settings = settings
        self.idle_sleep = idle_sleep
        self._offsets: dict[str, int] = {}
        self._webhook_cleared: set[str] = set()
        self._stop = threading.Event()

    def start(self) -> None:
        cycle = 0
        logger.info("Agent Telegram poller started.")
        while not self._stop.is_set():
            cycle += 1
            try:
                self._cycle(cycle)
            except Exception as exc:  # noqa: BLE001 - never let the loop die
                logger.error("Agent Telegram cycle %s failed: %s", cycle, exc, exc_info=True)
            self._stop.wait(self.idle_sleep)

    def stop(self) -> None:
        self._stop.set()

    def _cycle(self, cycle: int) -> None:
        agents = self._deployed_agents()
        if not agents:
            if cycle % 15 == 0:
                logger.info("Agent Telegram poll #%s: no deployed agents.", cycle)
            return
        for agent in agents:
            try:
                self._poll_agent(agent)
            except Exception as exc:  # noqa: BLE001 - isolate per-agent failures
                logger.warning("Agent %s Telegram poll failed: %s", agent.get("id"), exc)

    def _deployed_agents(self) -> list[JsonObject]:
        result: list[JsonObject] = []
        for agent in self.agent_store.list_agents(status="active"):
            agent_id = str(agent.get("id") or "")
            if not agent_id:
                continue
            tg = self.agent_store.get_telegram_config(agent_id)
            if not tg:
                continue
            status = str(tg.get("deploymentStatus", "")).lower()
            # "connected" = bot token verified (the normal live state);
            # "deployed"/"active" = explicitly enabled. Anything else (e.g.
            # "disconnected") means the bot is not supposed to answer.
            if status not in ("connected", "deployed", "active"):
                continue
            if not tg.get("botToken"):
                continue
            result.append(agent)
        return result

    def _poll_agent(self, agent: JsonObject) -> None:
        agent_id = str(agent.get("id") or "")
        tg = self.agent_store.get_telegram_config(agent_id)
        if not tg:
            return
        token = str(tg.get("botToken") or "")
        if not token:
            return

        # A webhook on the same bot would prevent getUpdates from returning anything.
        if token not in self._webhook_cleared:
            try:
                _call_telegram(token, "deleteWebhook", {"drop_pending_updates": False})
            except Exception as exc:  # noqa: BLE001
                logger.warning("Agent %s deleteWebhook failed: %s", agent_id, exc)
            self._webhook_cleared.add(token)

        offset = self._offsets.get(agent_id)
        if offset is None:
            offset = int(tg.get("telegramOffset") or 0)

        updates = _get_updates(token, offset, timeout=0)
        if not updates:
            return

        next_offset = offset
        for update in updates:
            update_id = int(update.get("update_id", 0))
            next_offset = update_id + 1
            self._handle_update(agent, token, update)

        self._offsets[agent_id] = next_offset
        # Persist so a restart doesn't replay old messages.
        try:
            stored = int((self.agent_store.get_telegram_config(agent_id) or {}).get("telegramOffset") or 0)
            if next_offset > stored:
                self.agent_store.update_telegram_config(agent_id, {"telegramOffset": next_offset})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Agent %s offset persist failed: %s", agent_id, exc)

    def _handle_update(self, agent: JsonObject, token: str, update: JsonObject) -> None:
        message = next(
            (update.get(name) for name in ("message", "edited_message") if isinstance(update.get(name), dict)),
            None,
        )
        if not isinstance(message, dict):
            return

        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        # Agent bots only answer direct messages, never groups.
        if str(chat.get("type", "")).lower() != "private":
            return

        text = _extract_text(message)
        if not text:
            return

        chat_id = str(chat.get("id") or "")
        if not chat_id:
            return

        agent_id = str(agent.get("id") or "")
        logger.info("Agent %s Telegram DM from %s: %s", agent_id, _extract_sender(message), text[:80])

        reply, error = generate_agent_reply(self.agent_store, self.settings, agent, text)
        if error:
            logger.warning("Agent %s reply error: %s", agent_id, error)
            return

        html = _markdown_to_telegram_html(reply)
        if not html:
            return

        try:
            _call_telegram(token, "sendMessage", {"chat_id": chat_id, "text": html, "parse_mode": "HTML"})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Agent %s Telegram send failed: %s", agent_id, exc)
