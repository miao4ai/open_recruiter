"""One interface over the supported chat providers, via LiteLLM.

Two things matter here that the rest of the SDK depends on:

* **Tool calls are native.** The model is given real tool schemas and answers
  with structured calls, instead of being asked to emit JSON that we then parse
  with regex fallbacks.
* **Streaming is real.** `stream()` yields text as it arrives. Tool-call
  arguments arrive fragmented across chunks and are reassembled here, so
  callers only ever see a complete `ToolCall`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from openrecruiter.config import Config
from openrecruiter.events import TextDelta, ToolCall

log = logging.getLogger(__name__)

# Anthropic bills cached input tokens at a large discount. Caching is only worth
# a cache-write below roughly 1024 tokens, which is about this many characters.
_CACHE_MIN_CHARS = 4000


class LLMError(RuntimeError):
    """The provider call failed. The cause is chained."""


class LLM:
    """A thin, synchronous chat client.

    Synchronous on purpose: the work is one network call, and every host that
    needs concurrency already has its own way of getting it — a thread, a task
    group, an executor. Forcing async here would push that choice onto callers
    who do not need it.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    # ── message assembly ─────────────────────────────────────────────────

    def _system_message(self, system: str) -> dict:
        if self.config.llm_provider == "anthropic" and len(system) >= _CACHE_MIN_CHARS:
            return {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        return {"role": "system", "content": system}

    def _kwargs(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None,
        stream: bool,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.config.model_id,
            "messages": [self._system_message(system), *messages],
            "max_tokens": self.config.max_tokens,
        }
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if tools:
            kwargs["tools"] = tools
        if stream:
            kwargs["stream"] = True
        return kwargs

    # ── plain completions ────────────────────────────────────────────────

    def complete(self, system: str, messages: list[dict]) -> str:
        """Return the assistant's reply as text."""
        from litellm import completion

        try:
            resp = completion(**self._kwargs(system, messages, None, False))
        except Exception as exc:
            raise LLMError(f"{self.config.model_id}: {exc}") from exc
        return resp.choices[0].message.content or ""

    def complete_json(self, system: str, messages: list[dict]) -> Any:
        """Return the reply parsed as JSON.

        Providers differ in how reliably they honour a JSON instruction, so the
        request asks for JSON *and* the response is tolerated with code fences
        around it.
        """
        from litellm import completion

        system = (
            system
            + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown fences, no explanation."
        )
        messages = [m.copy() for m in messages]
        for m in reversed(messages):
            if m.get("role") == "user" and "json" not in str(m.get("content", "")).lower():
                m["content"] = f"{m['content']}\n\n[Respond in JSON format.]"
                break

        kwargs = self._kwargs(system, messages, None, False)
        kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = completion(**kwargs)
        except Exception as exc:
            raise LLMError(f"{self.config.model_id}: {exc}") from exc

        raw = (resp.choices[0].message.content or "").strip()
        return _loads_lenient(raw)

    # ── streaming, with tool calls ───────────────────────────────────────

    def stream(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Iterator[TextDelta | ToolCall]:
        """Yield text as it arrives, then any tool calls the model asked for.

        Tool calls are yielded only once complete: providers stream a call's
        arguments as JSON fragments, and a half-parsed argument object is worse
        than no event at all.
        """
        from litellm import completion

        try:
            resp = completion(**self._kwargs(system, messages, tools, True))
        except Exception as exc:
            raise LLMError(f"{self.config.model_id}: {exc}") from exc

        # index -> {"id", "name", "arguments"}; providers key fragments by index.
        pending: dict[int, dict[str, str]] = {}

        for chunk in resp:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue

            text = getattr(delta, "content", None)
            if text:
                yield TextDelta(text=text)

            for frag in getattr(delta, "tool_calls", None) or []:
                slot = pending.setdefault(
                    getattr(frag, "index", 0) or 0,
                    {"id": "", "name": "", "arguments": ""},
                )
                if getattr(frag, "id", None):
                    slot["id"] = frag.id
                fn = getattr(frag, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        slot["arguments"] += fn.arguments

        for index in sorted(pending):
            slot = pending[index]
            if not slot["name"]:
                continue
            yield ToolCall(
                id=slot["id"] or f"call_{index}",
                name=slot["name"],
                arguments=_loads_arguments(slot["arguments"], slot["name"]),
            )


def _loads_lenient(raw: str) -> Any:
    """Parse JSON that may still be wrapped in a markdown fence."""
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    return json.loads(raw)


def _loads_arguments(raw: str, tool_name: str) -> dict:
    """Tool arguments, or an empty dict if the model produced nothing usable.

    A malformed argument blob should surface as the tool rejecting its input,
    not as an exception tearing down the whole stream.
    """
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Tool %s: could not parse arguments %r", tool_name, raw[:200])
        return {}
    return parsed if isinstance(parsed, dict) else {}


__all__ = ["LLM", "LLMError"]
