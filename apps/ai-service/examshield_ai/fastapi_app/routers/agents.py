"""Community-agent CRUD, knowledge, deploy, test, and conversation routes."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, Depends, Request

from examshield_ai.llm_providers import ProviderConfig, list_providers, validate_api_key
from examshield_ai.llm_providers import chat_completion as provider_chat_completion
from examshield_ai.multipart_parse import parse_multipart
from examshield_ai.normalize import normalize_api_key
from examshield_ai.rag import (
    RAGConfig,
    chunk_text,
    extract_text_from_file,
    ingest_knowledge_source,
    search_agent_knowledge,
)
from examshield_ai.response_cache import cached_get
from examshield_ai.store import UploadedFile

from ..deps import backend_secret, body_size_guard
from ..responses import json_response

router = APIRouter()


async def _read_json(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _core(request: Request):
    return request.app.state.core


@router.get("/llm/providers")
async def providers(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    return json_response(
        cached_get(core.read_cache, request.url.path, lambda: {"providers": list_providers()}),
        request=request,
    )


@router.post("/llm/validate")
async def validate_llm_key(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    data = await _read_json(request)
    provider = str(data.get("provider", "")).strip()
    api_key = str(data.get("apiKey", "")).strip()
    model = str(data.get("model", "")).strip()
    endpoint_url = str(data.get("endpointUrl", "")).strip()

    if not provider:
        return json_response({"error": "provider is required."}, status=400, request=request)
    if provider != "custom" and not api_key:
        return json_response({"error": "apiKey is required for this provider."}, status=400, request=request)
    if provider == "custom" and not endpoint_url:
        return json_response({"error": "endpointUrl is required for custom provider."}, status=400, request=request)
    if not model:
        from examshield_ai.llm_providers import PROVIDER_REGISTRY

        models = PROVIDER_REGISTRY.get(provider, {}).get("models", [])
        model = models[0] if models else "gpt-4o"

    config = ProviderConfig(provider=provider, api_key=api_key, model=model, endpoint_url=endpoint_url)
    result = validate_api_key(config)
    return json_response(result, request=request)


@router.get("/agents")
async def list_agents(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    status = request.query_params.get("status")
    agents = cached_get(
        core.read_cache,
        request.url.path + (("?" + request.url.query) if request.url.query else ""),
        lambda: core.agent_store.list_agents(status=status),
    )
    return json_response({"agents": agents, "total": len(agents)}, request=request)


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    agent = core.agent_store.get_agent(agent_id)
    if not agent:
        return json_response({"error": "Agent not found."}, status=404, request=request)
    llm_config = core.agent_store.get_llm_config(agent_id)
    tg_config = core.agent_store.get_telegram_config(agent_id)
    sources = core.agent_store.list_knowledge_sources(agent_id)
    stats = core.agent_store.get_agent_stats(agent_id)
    safe_telegram = None
    if tg_config:
        safe_telegram = {k: v for k, v in tg_config.items() if k != "botToken"}
        safe_telegram["botTokenSet"] = bool(tg_config.get("botToken"))
    return json_response(
        {
            "agent": {
                **agent,
                "knowledgeCount": stats["totalKnowledgeSources"],
                "conversationCount": stats["totalConversations"],
            },
            "llmConfig": {k: v for k, v in (llm_config or {}).items() if k != "apiKeyEncrypted"} if llm_config else None,
            "telegramConfig": safe_telegram,
            "knowledgeSources": sources,
            "stats": stats,
        },
        request=request,
    )


@router.post("/agents")
async def create_agent(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    data = await _read_json(request)
    agent = core.agent_store.create_agent(data)
    return json_response({"agent": agent, "message": "Agent created."}, status=201, request=request)


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    data = await _read_json(request)
    try:
        agent = core.agent_store.update_agent(agent_id, data)
        return json_response({"agent": agent, "message": "Agent updated."}, request=request)
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)
    except Exception:
        return json_response({"error": "Failed to update agent."}, status=400, request=request)


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    if core.agent_store.delete_agent(agent_id):
        return json_response({"message": "Agent deleted."}, request=request)
    return json_response({"error": "Agent not found."}, status=404, request=request)


@router.post("/agents/{agent_id}/llm")
async def upsert_agent_llm(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    data = await _read_json(request)
    try:
        config = core.agent_store.upsert_llm_config(agent_id, data)
        return json_response(
            {"config": {k: v for k, v in config.items() if k != "apiKeyEncrypted"}, "message": "LLM config saved."},
            request=request,
        )
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)
    except Exception:
        return json_response({"error": "Failed to save LLM config."}, status=400, request=request)


@router.post("/agents/{agent_id}/telegram")
async def upsert_agent_telegram(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    data = await _read_json(request)
    try:
        config = core.agent_store.upsert_telegram_config(agent_id, data)
        safe_config = {k: v for k, v in config.items() if k != "botToken"}
        safe_config["botTokenSet"] = bool(config.get("botToken"))
        return json_response({"config": safe_config, "message": "Telegram config saved."}, request=request)
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)
    except Exception:
        return json_response({"error": "Failed to save Telegram config."}, status=400, request=request)


@router.get("/agents/{agent_id}/knowledge")
async def list_knowledge(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    sources = core.agent_store.list_knowledge_sources(agent_id)
    return json_response({"sources": sources, "total": len(sources)}, request=request)


@router.post("/agents/{agent_id}/knowledge")
async def create_knowledge(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    data = await _read_json(request)
    try:
        source = core.agent_store.create_knowledge_source(agent_id, data)
        return json_response({"source": source, "message": "Knowledge source created."}, status=201, request=request)
    except LookupError:
        return json_response({"error": "Not found."}, status=404, request=request)
    except Exception:
        return json_response({"error": "Failed to create knowledge source."}, status=400, request=request)


@router.delete("/agents/{agent_id}/knowledge/{source_id}")
async def delete_knowledge(agent_id: str, source_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    source = core.agent_store.get_knowledge_source(source_id)
    if not source or source.get("agentId") != agent_id:
        return json_response({"error": "Knowledge source not found."}, status=404, request=request)
    core.agent_store.delete_knowledge_source(source_id)
    return json_response({"message": "Knowledge source deleted."}, request=request)


@router.post("/agents/{agent_id}/knowledge/{source_id}/upload")
async def upload_knowledge(
    agent_id: str,
    source_id: str,
    request: Request,
    _secret: None = Depends(backend_secret),
    _body: None = Depends(body_size_guard),
) -> dict:
    core = _core(request)
    source = core.agent_store.get_knowledge_source(source_id)
    if not source or source.get("agentId") != agent_id:
        return json_response({"error": "Knowledge source not found."}, status=404, request=request)

    core.agent_store.update_knowledge_source(source_id, {"status": "processing"})
    content_type = (request.headers.get("Content-Type") or "").lower()
    if "multipart/form-data" not in content_type:
        return json_response({"error": "multipart/form-data required."}, status=400, request=request)

    fields = parse_multipart(await request.body(), request.headers.get("Content-Type") or "")
    files_data = []
    for value in fields.values():
        if isinstance(value, UploadedFile) and value.data:
            files_data.append({"filename": value.filename, "data": value.data, "contentType": value.content_type})

    if not files_data:
        core.agent_store.update_knowledge_source(source_id, {"status": "failed", "errorMessage": "No files uploaded."})
        return json_response({"error": "No files uploaded."}, status=400, request=request)

    core.agent_store.update_knowledge_source(source_id, {"fileCount": len(files_data)})

    rag_config = RAGConfig(
        supabase_url=core.settings.supabase_url or "",
        supabase_service_role_key=core.settings.supabase_service_role_key or "",
        embed_function_url=f"{core.settings.supabase_url}/functions/v1/embed" if core.settings.supabase_url else "",
    )

    result: dict[str, Any] | None = None
    if rag_config.supabase_url and rag_config.supabase_service_role_key:
        result = ingest_knowledge_source(source_id, agent_id, files_data, rag_config)

    if not result or result.get("status") != "ready":
        local_chunks: list[dict[str, Any]] = []
        total_chars = 0
        for file_info in files_data:
            extracted = extract_text_from_file(
                str(file_info.get("filename") or ""),
                file_info.get("data") or b"",
                str(file_info.get("contentType") or "application/octet-stream"),
            )
            if not extracted:
                continue
            total_chars += len(extracted)
            for item in chunk_text(extracted):
                local_chunks.append({**item, "filename": file_info.get("filename", "")})
        if not local_chunks:
            message = "No text could be extracted from the uploaded files. Use PDF, TXT, or Markdown files with selectable text."
            core.agent_store.update_knowledge_source(source_id, {"status": "failed", "errorMessage": message})
            return json_response({"error": message}, status=400, request=request)
        stored = core.agent_store.replace_knowledge_chunks(source_id, agent_id, local_chunks)
        result = {"status": "ready", "chunksStored": stored, "totalChars": total_chars, "storage": "local"}

    core.agent_store.update_knowledge_source(source_id, {
        "status": "ready",
        "chunkCount": int(result.get("chunksStored") or 0),
        "totalChars": int(result.get("totalChars") or 0),
        "errorMessage": None,
    })
    return json_response(result, request=request)


@router.post("/agents/{agent_id}/test")
async def test_agent(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    data = await _read_json(request)
    question = str(data.get("question", "")).strip()
    if not question:
        return json_response({"error": "question is required."}, status=400, request=request)

    agent = core.agent_store.get_agent(agent_id)
    if not agent:
        return json_response({"error": "Agent not found."}, status=404, request=request)

    llm_config = core.agent_store.get_llm_config(agent_id)
    if not llm_config:
        return json_response({"error": "LLM not configured for this agent."}, status=400, request=request)

    rag_config = RAGConfig(
        supabase_url=core.settings.supabase_url or "",
        supabase_service_role_key=core.settings.supabase_service_role_key or "",
        embed_function_url=f"{core.settings.supabase_url}/functions/v1/embed" if core.settings.supabase_url else "",
    )

    context_chunks: list[dict[str, Any]] = []
    if rag_config.supabase_url:
        try:
            context_chunks = search_agent_knowledge(question, agent_id, rag_config)
        except Exception:
            pass
    if not context_chunks:
        context_chunks = core.agent_store.search_knowledge_chunks(agent_id, question)

    system_prompt = agent.get("systemPrompt", "") or "You are a helpful assistant."
    if context_chunks:
        context_text = "\n\n".join(c.get("content", "") for c in context_chunks)
        system_prompt += f"\n\nUse the following knowledge to answer:\n\n{context_text}"

    style = agent.get("responseStyle", "balanced")
    if style == "short":
        system_prompt += "\n\nKeep responses concise (1-2 paragraphs)."
    elif style == "detailed":
        system_prompt += "\n\nProvide detailed, comprehensive answers."
    if agent.get("citationMode") and context_chunks:
        system_prompt += "\n\nCite sources when referencing specific information."

    provider_config = ProviderConfig(
        provider=llm_config.get("provider", "openai"),
        api_key=normalize_api_key(llm_config),
        model=llm_config.get("model", "gpt-4o"),
        endpoint_url=llm_config.get("endpointUrl", ""),
        extra_headers=llm_config.get("extraHeaders", {}),
    )

    start = time.monotonic()
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    result = provider_chat_completion(provider_config, messages, max_tokens=1024, timeout=15)
    latency_ms = int((time.monotonic() - start) * 1000)

    response_text = result.get("content", "")
    if result.get("error"):
        return json_response(
            {
                "error": f"{provider_config.provider} request failed: {result['error']}",
                "provider": provider_config.provider,
                "model": provider_config.model,
            },
            status=502,
            request=request,
        )
    if not str(response_text).strip():
        return json_response({"error": "The configured model returned an empty response."}, status=502, request=request)

    core.agent_store.log_conversation(
        agent_id=agent_id,
        user_message=question,
        agent_response=response_text,
        sources=[{"content": c.get("content", "")[:200], "similarity": c.get("similarity", 0)} for c in context_chunks],
        latency_ms=latency_ms,
    )
    return json_response(
        {
            "response": response_text,
            "sources": context_chunks,
            "latencyMs": latency_ms,
            "model": provider_config.model,
            "provider": provider_config.provider,
        },
        request=request,
    )


@router.post("/agents/{agent_id}/deploy")
async def deploy_agent(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    agent = core.agent_store.get_agent(agent_id)
    if not agent:
        return json_response({"error": "Agent not found."}, status=404, request=request)

    llm_config = core.agent_store.get_llm_config(agent_id)
    if not llm_config:
        return json_response({"error": "LLM not configured. Complete provider setup first."}, status=400, request=request)

    telegram_config = core.agent_store.get_telegram_config(agent_id)
    if not telegram_config or not telegram_config.get("botToken"):
        return json_response({"error": "Telegram not configured. Add a bot token first."}, status=400, request=request)

    core.agent_store.update_agent(agent_id, {"status": "deploying"})
    token = telegram_config["botToken"]
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if not result.get("ok"):
                core.agent_store.update_agent(agent_id, {"status": "failed"})
                core.agent_store.update_telegram_config(agent_id, {"deploymentStatus": "invalid-token"})
                return json_response({"error": "Bot token is invalid."}, status=400, request=request)
    except Exception:
        core.agent_store.update_agent(agent_id, {"status": "failed"})
        core.agent_store.update_telegram_config(agent_id, {"deploymentStatus": "network-error"})
        return json_response({"error": "Failed to verify bot with Telegram."}, status=500, request=request)

    webhook_url = f"{core.settings.public_url}/telegram/webhook" if core.settings.public_url else ""
    if webhook_url:
        set_url = f"https://api.telegram.org/bot{token}/setWebhook"
        set_body = json.dumps({"url": webhook_url}).encode()
        set_req = urllib.request.Request(set_url, data=set_body, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(set_req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                if not result.get("ok"):
                    core.agent_store.update_agent(agent_id, {"status": "failed"})
                    return json_response(
                        {"error": f"Webhook setup failed: {result.get('description', 'unknown')}"},
                        status=500,
                        request=request,
                    )
        except Exception as exc:
            core.agent_store.update_agent(agent_id, {"status": "failed"})
            return json_response({"error": f"Webhook setup failed: {exc}"}, status=500, request=request)

    core.agent_store.update_agent(agent_id, {"status": "active"})
    core.agent_store.update_telegram_config(agent_id, {
        "deploymentStatus": "deployed",
        "botVerified": True,
        "webhookUrl": webhook_url,
    })
    return json_response(
        {"message": "Agent deployed successfully.", "status": "active", "webhookUrl": webhook_url},
        request=request,
    )


@router.get("/agents/{agent_id}/stats")
async def agent_stats(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    return json_response(core.agent_store.get_agent_stats(agent_id), request=request)


@router.get("/agents/{agent_id}/conversations")
async def agent_conversations(agent_id: str, request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    convs = core.agent_store.list_conversations(agent_id)
    return json_response({"conversations": convs, "total": len(convs)}, request=request)


@router.post("/telegram/verify-bot")
async def verify_bot(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    data = await _read_json(request)
    token = str(data.get("token", "")).strip()
    if not token:
        return json_response({"error": "Bot token is required."}, status=400, request=request)
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                bot = result.get("result", {})
                return json_response(
                    {
                        "valid": True,
                        "botUsername": bot.get("username", ""),
                        "botFirstName": bot.get("first_name", ""),
                        "botId": bot.get("id"),
                        "canJoinGroups": bot.get("can_join_groups", False),
                        "canReadAllGroupMessages": bot.get("can_read_all_group_messages", False),
                    },
                    request=request,
                )
            return json_response({"valid": False, "error": result.get("description", "Invalid token.")}, request=request)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return json_response({"valid": False, "error": "Invalid bot token."}, request=request)
        return json_response({"valid": False, "error": f"Telegram API error ({exc.code})."}, request=request)
    except urllib.error.URLError:
        return json_response({"valid": False, "error": "Network error reaching Telegram API."}, request=request)


@router.post("/telegram/chat")
async def test_telegram_chat(request: Request, _secret: None = Depends(backend_secret)) -> dict:
    core = _core(request)
    payload = await _read_json(request)
    chat_id = str(payload.get("chatId") or core.settings.telegram_admin_chat_id or "").strip()
    message_text = str(payload.get("message") or "").strip()
    if not chat_id or not message_text:
        return json_response({"error": "chatId and message are required."}, status=400, request=request)

    from examshield_ai.llm import KiloClient
    from examshield_ai.telegram import _clean_telegram_html

    llm = KiloClient(core.settings)
    if not llm.configured:
        return json_response({"error": "KILO_API_KEY is not configured."}, status=500, request=request)

    system_prompt = (
        "You are ExamShield AI, an exam security assistant. "
        "You are chatting with someone in a private Telegram DM. "
        "You monitor groups for potential exam leaks and suspicious activity. "
        "You are friendly, helpful, and professional. "
        "Respond naturally to questions about exam security, the monitoring system, or general queries. "
        "Keep responses concise (under 200 characters). "
        "Use Telegram HTML formatting: <b>, <i>, <code>. "
        "If someone asks what you do, briefly explain you monitor for exam leaks. "
        "If someone greets you, respond warmly. "
        "Be conversational and human-like."
    )
    try:
        response = llm.chat_text(
            model=core.settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User message: {message_text}"},
            ],
            max_tokens=200,
            timeout=10,
        )
    except Exception as exc:
        return json_response({"error": f"Chat request failed: {exc}"}, status=502, request=request)

    cleaned = _clean_telegram_html(response)
    telegram = core.telegram
    if telegram.configured:
        telegram.send_message(chat_id, cleaned, parse_mode="HTML")
    return json_response(
        {
            "status": "ok",
            "message": message_text,
            "chatId": chat_id,
            "response": cleaned or "No response generated",
            "sentToTelegram": telegram.configured,
        },
        request=request,
    )
