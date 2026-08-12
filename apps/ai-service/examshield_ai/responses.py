from __future__ import annotations

from .injection import SYSTEM_PROMPT_HARDENING, sanitize_input
from .store import JsonObject


def conversation_messages(
    prompt: str,
    history: list[JsonObject],
    operator: JsonObject | None = None,
) -> list[JsonObject]:
    system_prompt = (
        "You are EXAMSHIELD AI — the examination-security assistant and the user's sharpest colleague on this platform. "
        "You are confident, proactive, and genuinely useful: you lead with substance, not caveats, and you anticipate what the user actually needs. "
        "Speak in plain, natural language like a brilliant teammate — never like a chatbot, a form, or a disclaimer. "
        "Be concise by default, but go deep and thorough the moment the user wants detail.\n\n"
        "You know EXAMSHIELD inside out — its architecture, the evidence pipeline, OCR and watermark forensics, "
        "attribution, threat monitoring, and the agent system — so answer conceptual and how-to questions directly and with authority.\n\n"
        "FORMATTING — make every answer easy to scan:\n"
        "- Use **bold** for the key term, metric, status, or conclusion in each point.\n"
        "- Use short bullet lists (- ) for steps, options, or grouped facts; use numbered lists (1. ) for ordered sequences.\n"
        "- Use a clear one-line headline or lead sentence before details when the answer is more than two sentences.\n"
        "- Use `code` for commands, IDs, file names, and model/tool names.\n"
        "- Never wrap the whole answer in a code block. Never use markdown headings (#). Keep it tight and readable.\n\n"
        "About live operational data (current evidence, open alerts, compromised papers, registry threats, report status): "
        "only state specific figures or statuses when tool results are provided in the conversation. "
        "When they aren't, and the user is clearly asking about the live system, do NOT stall or refuse. "
        "Briefly note you don't have a live feed in this chat, then immediately be useful: explain what's normally monitored, "
        "point them to the exact command or dashboard to check (e.g. 'show recent evidence', 'list threats', 'generate report'), "
        "and offer to pull it for them. It is always better to guide the user to the real data than to guess at it.\n\n"
        "Never invent IDs, counts, or case details you weren't given. Be human, be bold, be useful.\n\n"
        "Always complete your answer — never stop mid-sentence or mid-word. "
        "If a topic is large, summarize and offer to go deeper rather than cutting off."
        + SYSTEM_PROMPT_HARDENING
    )
    operator_intro = _operator_intro(operator)
    if operator_intro:
        system_prompt += "\n\n" + operator_intro
    return [
        {"role": "system", "content": system_prompt},
        *history_messages(history),
        {"role": "user", "content": sanitize_input(prompt)},
    ]


def grounded_system_message() -> str:
    """System instructions for answering strictly from retrieved live data."""
    return (
        "You are EXAMSHIELD AI, a national examination security analyst helping an investigator. "
        "Live data was just retrieved about the investigation. Use ONLY that data to answer naturally. "
        "Speak like a knowledgeable colleague explaining findings — not a report generator. "
        "Be concise, direct, and conversational. "
        "Follow summary, threatPosture, and metrics exactly — never contradict them. "
        "If threatPosture is elevated, say the posture is elevated even when openAlerts is zero. "
        "Open forensic alerts and registry threats are different: zero open alerts does not mean stable if registry threats exist. "
        "If papers are compromised, explain what that means in context. "
        "Never fabricate details not in the tool data. If something is unknown, say so. "
        "No bullet points, no markdown, no tables — just natural flowing text."
    )


def _operator_intro(operator: JsonObject | None) -> str:
    """Build the one-line operator identity note appended to the system prompt.

    Returns empty string when no usable operator context is present so callers
    that pass ``None`` (e.g. the old zero-arg behaviour) stay unchanged.
    """
    if not isinstance(operator, dict):
        return ""
    name = str(operator.get("name") or "").strip()
    role = str(operator.get("role") or "Operator").strip() or "Operator"
    if not name and not operator.get("email"):
        return ""
    if name:
        return (
            f"You are speaking with {name} (role: {role}). "
            "Address them by name when natural — use their name in greetings and sign-offs."
        )
    return (
        f"You are speaking with the operator whose account is {operator.get('email')} "
        f"(role: {role}). Address them as the operator."
    )


def grounded_messages(prompt: str, history: list[JsonObject], tool_context: str) -> list[JsonObject]:
    return [
        {
            "role": "system",
            "content": grounded_system_message() + SYSTEM_PROMPT_HARDENING,
        },
        *history_messages(history),
        {
            "role": "user",
            "content": "\n".join(
                [
                    f"Investigator asked: {sanitize_input(prompt)}",
                    "",
                    "Here is the live data returned by the tool:",
                    sanitize_input(tool_context),
                    "",
                    "Respond naturally based on this data. Answer the investigator's actual question."
                ]
            ),
        },
    ]


def history_messages(history: list[JsonObject]) -> list[JsonObject]:
    messages: list[JsonObject] = []
    for item in history[-6:]:
        role = "user" if item.get("role") == "operator" else "assistant"
        content = str(item.get("content") or "")
        if content:
            messages.append({"role": role, "content": content})
    return messages
