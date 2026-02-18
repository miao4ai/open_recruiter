"""Unified LLM interface supporting Anthropic and OpenAI."""

from __future__ import annotations

import json
from typing import Any

from app.config import Config


def _call_anthropic(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=cfg.anthropic_api_key)
    if json_mode:
        system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown fences, no explanation."
    resp = client.messages.create(
        model=cfg.llm_model, max_tokens=4096, system=system, messages=messages,
    )
    return resp.content[0].text


# Models that only work with the Responses API (not Chat Completions)
_RESPONSES_ONLY_MODELS = {"gpt-5.2-pro", "gpt-5.2-pro-2025-12-11"}


def _call_openai(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=cfg.openai_api_key)

    if cfg.llm_model in _RESPONSES_ONLY_MODELS:
        return _call_openai_responses(client, cfg.llm_model, system, messages, json_mode)

    full = [{"role": "system", "content": system}] + messages
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(model=cfg.llm_model, messages=full, max_completion_tokens=4096, **kwargs)
    return resp.choices[0].message.content or ""


def _call_openai_responses(client: Any, model: str, system: str, messages: list[dict], json_mode: bool = False) -> str:
    """Use the OpenAI Responses API for models that don't support Chat Completions."""
    if json_mode:
        system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown fences, no explanation."

    # Combine user messages into a single input
    user_text = "\n\n".join(m["content"] for m in messages if m.get("role") == "user")

    resp = client.responses.create(
        model=model,
        instructions=system,
        input=user_text,
    )
    return resp.output_text or ""


def chat(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> str:
    if cfg.llm_provider == "openai":
        return _call_openai(cfg, system, messages, json_mode)
    return _call_anthropic(cfg, system, messages, json_mode)


def chat_json(cfg: Config, system: str, messages: list[dict]) -> dict | list:
    raw = chat(cfg, system, messages, json_mode=True).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    return json.loads(raw)
