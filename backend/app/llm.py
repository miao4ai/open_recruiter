"""Unified LLM interface supporting Anthropic and OpenAI."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from app.config import Config


# ── Non-streaming calls ─────────────────────────────────────────────────

def _call_anthropic(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=cfg.anthropic_api_key)
    if json_mode:
        system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown fences, no explanation."
    resp = client.messages.create(
        model=cfg.llm_model, max_tokens=4096, system=system, messages=messages,
    )
    return resp.content[0].text


def _call_openai(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=cfg.openai_api_key)
    full = [{"role": "system", "content": system}] + messages
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(model=cfg.llm_model, messages=full, max_tokens=4096, **kwargs)
    return resp.choices[0].message.content or ""


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


# ── Streaming calls ─────────────────────────────────────────────────────

def _stream_anthropic(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> Iterator[str]:
    from anthropic import Anthropic

    client = Anthropic(api_key=cfg.anthropic_api_key)
    if json_mode:
        system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown fences, no explanation."
    with client.messages.stream(
        model=cfg.llm_model, max_tokens=4096, system=system, messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def _stream_openai(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> Iterator[str]:
    from openai import OpenAI

    client = OpenAI(api_key=cfg.openai_api_key)
    full = [{"role": "system", "content": system}] + messages
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(
        model=cfg.llm_model, messages=full, max_tokens=4096, stream=True, **kwargs,
    )
    for chunk in resp:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def chat_stream(cfg: Config, system: str, messages: list[dict], json_mode: bool = False) -> Iterator[str]:
    """Yield text chunks from the LLM (synchronous generator)."""
    if cfg.llm_provider == "openai":
        yield from _stream_openai(cfg, system, messages, json_mode)
    else:
        yield from _stream_anthropic(cfg, system, messages, json_mode)
