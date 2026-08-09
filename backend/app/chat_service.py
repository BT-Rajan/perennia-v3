"""
Orchestrates a single chat turn: reads chat.* config, calls the
configured LLM provider (or skips straight to the fallback message if
none is configured), and opportunistically captures a lead if the
visitor's message contains an email address - all in one place so
routers/public_chat.py stays a thin HTTP wrapper.
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app import leads_service, llm_client
from app.settings_service import get_setting

EMAIL_RE = re.compile(r"[^\s@,;:!?()<>\[\]\"']+@[^\s@,;:!?()<>\[\]\"']+\.[^\s@,;:!?()<>\[\]\"']+")


def _lang_value(value: dict, lang: str) -> str:
    return value.get(lang) or value.get("en") or next(iter(value.values()), "")


def get_reply(db: Session, *, message: str, lang: str, history: list[dict]) -> str:
    if not get_setting(db, "features.chat_enabled"):
        return _lang_value(get_setting(db, "chat.unavailable_message"), lang)

    provider = get_setting(db, "chat.llm_provider")
    unavailable = _lang_value(get_setting(db, "chat.unavailable_message"), lang)

    if provider == "none":
        reply = unavailable
    else:
        try:
            reply = llm_client.generate_reply(
                provider=provider,
                api_key=get_setting(db, "chat.llm_api_key"),
                model=get_setting(db, "chat.llm_model"),
                system_prompt=_lang_value(get_setting(db, "chat.system_prompt"), lang),
                history=history,
                message=message,
                max_tokens=get_setting(db, "chat.max_tokens"),
                temperature=get_setting(db, "chat.temperature"),
            )
        except llm_client.LLMError:
            reply = unavailable

    _maybe_capture_lead(db, message=message)
    return reply


def _maybe_capture_lead(db: Session, *, message: str) -> None:
    match = EMAIL_RE.search(message)
    if not match:
        return
    leads_service.capture_lead(
        db, email=match.group(0), source="chat",
        transcript_entry={"from": "user", "text": message},
    )
