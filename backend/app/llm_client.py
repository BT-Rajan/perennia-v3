"""
Thin, provider-abstracted client for the chat assistant's LLM calls.
Every provider detail (which one, which model, the key, sampling
params) comes from chat.* settings — see settings_registry.py — so
switching providers or models is an admin edit, not a deploy.

Deliberately not using either vendor's SDK: both APIs are a single
JSON POST, and a plain httpx call keeps this file's only dependency on
the wire format, not on SDK version churn.
"""
from __future__ import annotations

import httpx

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

REQUEST_TIMEOUT_SECONDS = 20.0


class LLMError(Exception):
    """Raised for any failure talking to the provider — network,
    auth, rate limit, malformed response. Callers (chat_service.py)
    catch this uniformly and fall back to chat.unavailable_message
    rather than ever surfacing a raw provider error to a visitor."""


def _history_to_messages(history: list[dict]) -> list[dict]:
    """Frontend history entries are {from: 'user'|'ai', text} (tests
    also pass 'assistant'). Anything not literally 'user' is the
    assistant's own prior turn — treating 'ai' as unrecognized used to
    silently relabel every past assistant reply as a 'user' message,
    corrupting multi-turn context sent to the LLM."""
    return [{"role": ("user" if h.get("from") == "user" else "assistant"), "content": h.get("text", "")}
            for h in history]


def _call_anthropic(*, api_key: str, model: str, system_prompt: str, history: list[dict], message: str,
                     max_tokens: int, temperature: float) -> str:
    messages = _history_to_messages(history) + [{"role": "user", "content": message}]
    try:
        resp = httpx.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "system": system_prompt,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        text = "".join(parts).strip()
        if not text:
            raise LLMError("Anthropic response contained no text content")
        return text
    except httpx.HTTPStatusError as e:
        raise LLMError(f"Anthropic API returned {e.response.status_code}") from e
    except httpx.HTTPError as e:
        raise LLMError(f"Anthropic API request failed: {e}") from e


def _call_openai(*, api_key: str, model: str, system_prompt: str, history: list[dict], message: str,
                  max_tokens: int, temperature: float) -> str:
    messages = [{"role": "system", "content": system_prompt}, *_history_to_messages(history),
                {"role": "user", "content": message}]
    try:
        resp = httpx.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        if not text:
            raise LLMError("OpenAI response contained no text content")
        return text
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected OpenAI response shape: {e}") from e
    except httpx.HTTPStatusError as e:
        raise LLMError(f"OpenAI API returned {e.response.status_code}") from e
    except httpx.HTTPError as e:
        raise LLMError(f"OpenAI API request failed: {e}") from e


_PROVIDERS = {"anthropic": _call_anthropic, "openai": _call_openai}


def generate_reply(*, provider: str, api_key: str, model: str, system_prompt: str, history: list[dict],
                    message: str, max_tokens: int, temperature: float) -> str:
    if provider not in _PROVIDERS:
        raise LLMError(f"Unsupported or unconfigured provider: {provider!r}")
    if not api_key:
        raise LLMError("No API key configured")
    return _PROVIDERS[provider](
        api_key=api_key, model=model, system_prompt=system_prompt, history=history,
        message=message, max_tokens=max_tokens, temperature=temperature,
    )
