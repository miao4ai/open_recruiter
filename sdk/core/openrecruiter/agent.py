"""The agent loop.

The model is given real tools and decides for itself what to call, in what
order, and when it is finished. That is the whole difference from asking a model
to emit an action name and dispatching it: a single request can retrieve a job,
rank the pool, read the top result, and draft three emails, because each tool
result feeds the next decision.

The loop is a generator of `Event`s so a caller can render text as it arrives
rather than after the whole turn completes, and so it can stop at an approval
gate without the agent needing to know what a user interface is.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from pydantic import BaseModel, Field

from openrecruiter.events import (
    ApprovalRequired,
    Event,
    Finished,
    TextDelta,
    ToolCall,
    ToolResult,
)
from openrecruiter.prompts import AGENT_SYSTEM
from openrecruiter.providers.llm import LLM, LLMError
from openrecruiter.tools.base import ToolError, ToolRegistry

log = logging.getLogger(__name__)

DEFAULT_MAX_STEPS = 8


class PendingApproval(BaseModel):
    """Everything needed to carry on once a human has decided.

    A plain model rather than a closure, because the decision usually arrives on
    a later HTTP request in a different process. Store it, then hand it back to
    `resume()`.
    """

    messages: list[dict] = Field(default_factory=list)
    tool_name: str = ""
    tool_call_id: str = ""
    arguments: dict = Field(default_factory=dict)
    #: Calls the model made in the same turn that have not run yet.
    queued: list[dict] = Field(default_factory=list)
    step: int = 0


class Agent:
    """Runs a conversation with tools until the work is done."""

    def __init__(
        self,
        llm: LLM,
        tools: ToolRegistry,
        system: str = AGENT_SYSTEM,
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.system = system
        self.max_steps = max_steps
        #: Set when a run stops at an approval gate; None otherwise.
        self.pending: PendingApproval | None = None

    # ── entry points ─────────────────────────────────────────────────────

    def run(self, message: str, history: list[dict] | None = None) -> Iterator[Event]:
        """Answer `message`, calling tools as needed."""
        messages = [*(history or []), {"role": "user", "content": message}]
        self.pending = None
        yield from self._loop(messages, step=0)

    def resume(self, pending: PendingApproval, approved: bool) -> Iterator[Event]:
        """Continue a run that stopped for approval.

        Declining is not an error: the model is told the user refused and gets to
        respond to that, which is usually more useful than an abandoned turn.
        """
        self.pending = None
        messages = list(pending.messages)

        if approved:
            result = self._invoke(pending.tool_name, pending.arguments)
            yield result
            messages.append(_tool_message(pending.tool_call_id, result))
        else:
            declined = ToolResult(
                id=pending.tool_call_id,
                name=pending.tool_name,
                error="The user declined this action. It was not performed.",
            )
            yield declined
            messages.append(_tool_message(pending.tool_call_id, declined))

        queued = [ToolCall(**c) for c in pending.queued]
        stopped = yield from self._run_tools(queued, messages, pending.step)
        if stopped:
            return
        yield from self._loop(messages, step=pending.step + 1)

    # ── the loop ─────────────────────────────────────────────────────────

    def _loop(self, messages: list[dict], step: int) -> Iterator[Event]:
        schemas = self.tools.schemas()

        while step < self.max_steps:
            text_parts: list[str] = []
            calls: list[ToolCall] = []

            try:
                for event in self.llm.stream(self.system, messages, tools=schemas):
                    if isinstance(event, TextDelta):
                        text_parts.append(event.text)
                        yield event
                    else:
                        calls.append(event)
            except LLMError as exc:
                log.error("Agent step %d failed: %s", step, exc)
                yield Finished(text="".join(text_parts), stop_reason="error", steps=step, error=str(exc))
                return

            text = "".join(text_parts)

            if not calls:
                yield Finished(text=text, stop_reason="end_turn", steps=step)
                return

            messages.append(_assistant_message(text, calls))

            stopped = yield from self._run_tools(calls, messages, step)
            if stopped:
                return
            step += 1

        yield Finished(stop_reason="max_steps", steps=step)

    def _run_tools(
        self, calls: list[ToolCall], messages: list[dict], step: int
    ) -> Iterator[Event]:
        """Run each call in order. Returns True if the run stopped for approval.

        Anything queued behind an approval gate is carried into `PendingApproval`
        rather than run — the user has not agreed to those either, and running
        them would make the gate cosmetic.
        """
        for i, call in enumerate(calls):
            if self._needs_approval(call.name):
                self.pending = PendingApproval(
                    messages=messages,
                    tool_name=call.name,
                    tool_call_id=call.id,
                    arguments=call.arguments,
                    queued=[
                        {"id": c.id, "name": c.name, "arguments": c.arguments}
                        for c in calls[i + 1 :]
                    ],
                    step=step,
                )
                yield ApprovalRequired(
                    id=call.id,
                    name=call.name,
                    arguments=call.arguments,
                    description=self.tools.get(call.name).description,
                )
                yield Finished(stop_reason="awaiting_approval", steps=step)
                return True

            # Announced before it runs, so a caller can show what is happening
            # rather than a spinner — a rank over a large pool is not instant.
            yield call

            result = self._invoke(call.name, call.arguments, call_id=call.id)
            yield result
            messages.append(_tool_message(call.id, result))

        return False

    # ── helpers ──────────────────────────────────────────────────────────

    def _needs_approval(self, name: str) -> bool:
        try:
            return self.tools.get(name).requires_approval
        except ToolError:
            return False

    def _invoke(self, name: str, arguments: dict, call_id: str = "") -> ToolResult:
        """Call a tool, turning any failure into a result the model can read.

        A tool raising must not end the turn: the model can often recover — fix
        an argument, try a different tool — if it is told what went wrong.
        """
        try:
            value = self.tools.call(name, arguments)
        except ToolError as exc:
            return ToolResult(id=call_id, name=name, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - tools are arbitrary user code
            log.exception("Tool %s raised", name)
            return ToolResult(id=call_id, name=name, error=f"{type(exc).__name__}: {exc}")
        return ToolResult(id=call_id, name=name, result=value)


# ── provider message shapes ──────────────────────────────────────────────


def _assistant_message(text: str, calls: list[ToolCall]) -> dict:
    return {
        "role": "assistant",
        "content": text or None,
        "tool_calls": [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
            }
            for c in calls
        ],
    }


def _tool_message(call_id: str, result: ToolResult) -> dict:
    payload = {"error": result.error} if result.error else {"result": result.result}
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps(payload, default=str),
    }


__all__ = ["Agent", "PendingApproval", "DEFAULT_MAX_STEPS"]
