"""Unified LLM interface via LiteLLM — supports 100+ providers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from app.config import Config


def _model_name(cfg: Config) -> str:
    """Build the LiteLLM model string (e.g. 'anthropic/claude-sonnet-4-20250514')."""
    model = cfg.llm_model
    # If user already included a provider prefix, use as-is
    if "/" in model:
        return model
    # Otherwise, prepend the provider prefix
    provider = cfg.llm_provider
    if provider == "anthropic":
        return f"anthropic/{model}"
    elif provider == "openai":
        return f"openai/{model}"
    elif provider == "gemini":
        return f"gemini/{model}"
    # Fallback: pass model name directly, let litellm figure it out
    return model


def _api_key(cfg: Config) -> str | None:
    """Return the appropriate API key for the provider."""
    provider = cfg.llm_provider
    if provider == "anthropic":
        return cfg.anthropic_api_key or None
    elif provider == "openai":
        return cfg.openai_api_key or None
    elif provider == "gemini":
        return cfg.gemini_api_key or None
    return None


# ── Non-streaming calls ─────────────────────────────────────────────────

def _prepare_json_mode(system: str, messages: list[dict]) -> tuple[str, list[dict]]:
    """Inject JSON instructions into both system and the last user message.

    OpenAI's Responses API requires the word 'json' in user input,
    not just in the system prompt. This ensures all providers work.
    """
    system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown fences, no explanation."
    messages = [m.copy() for m in messages]
    # Ensure the last user message mentions JSON
    for m in reversed(messages):
        if m.get("role") == "user" and "json" not in m.get("content", "").lower():
            m["content"] += "\n\n[Respond in JSON format.]"
            break
    return system, messages


def chat(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> str:
    from litellm import completion

    if json_mode:
        system, messages = _prepare_json_mode(system, messages)

    kwargs: dict[str, Any] = {
        "model": _model_name(cfg),
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 4096,
    }

    api_key = _api_key(cfg)
    if api_key:
        kwargs["api_key"] = api_key

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = completion(**kwargs)
    return resp.choices[0].message.content or ""


def chat_json(cfg: Config, system: str, messages: list[dict]) -> dict | list:
    raw = chat(cfg, system, messages, json_mode=True).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    return json.loads(raw)


# ── Streaming calls ─────────────────────────────────────────────────────

def chat_stream(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> Iterator[str]:
    """Yield text chunks from the LLM (synchronous generator)."""
    from litellm import completion

    if json_mode:
        system, messages = _prepare_json_mode(system, messages)

    kwargs: dict[str, Any] = {
        "model": _model_name(cfg),
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 4096,
        "stream": True,
    }

    api_key = _api_key(cfg)
    if api_key:
        kwargs["api_key"] = api_key

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = completion(**kwargs)
    for chunk in resp:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
