"""Unified LLM interface supporting Anthropic and OpenAI."""

from __future__ import annotations

import json
from typing import Any

from open_recruiter.config import Config


def _call_anthropic(config: Config, system: str, messages: list[dict], json_mode: bool = False) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=config.anthropic_api_key)
    if json_mode:
        system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation."

    resp = client.messages.create(
        model=config.llm_model,
        max_tokens=4096,
        system=system,
        messages=messages,
    )
    return resp.content[0].text


def _call_openai(config: Config, system: str, messages: list[dict], json_mode: bool = False) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=config.openai_api_key)
    full_messages = [{"role": "system", "content": system}] + messages

    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(
        model=config.llm_model,
        messages=full_messages,
        max_tokens=4096,
        **kwargs,
    )
    return resp.choices[0].message.content or ""


def chat(config: Config, system: str, messages: list[dict], json_mode: bool = False) -> str:
    """Send a chat request to the configured LLM provider.

    Args:
        config: Application configuration.
        system: System prompt.
        messages: List of {"role": ..., "content": ...} dicts.
        json_mode: If True, request JSON output.

    Returns:
        The assistant's text response.
    """
    if config.llm_provider == "openai":
        return _call_openai(config, system, messages, json_mode)
    return _call_anthropic(config, system, messages, json_mode)


def chat_json(config: Config, system: str, messages: list[dict]) -> dict:
    """Call the LLM and parse the response as JSON."""
    raw = chat(config, system, messages, json_mode=True)
    # Strip potential markdown code fences
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)
