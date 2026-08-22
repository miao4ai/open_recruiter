"""Events emitted while the agent works.

The agent is a generator of these rather than a function returning a string, so
a caller can render tokens as they arrive, show a tool running, and stop the
whole thing at an approval gate. A host maps them onto whatever transport it
uses — SSE, a websocket, or a terminal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class TextDelta:
    """A fragment of the assistant's reply, as it is generated."""

    text: str
    type: Literal["text_delta"] = "text_delta"


@dataclass
class ToolCall:
    """The model asked for a tool. Arguments are already parsed."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    type: Literal["tool_call"] = "tool_call"


@dataclass
class ToolResult:
    """A tool ran. `error` is set instead of `result` when it raised."""

    id: str
    name: str
    result: Any = None
    error: str = ""
    type: Literal["tool_result"] = "tool_result"

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass
class ApprovalRequired:
    """A tool marked `requires_approval` is ready to run and is waiting.

    The agent stops here. Resuming means calling the agent again with this call
    id in `approved`, which is what makes the gate meaningful — a caller that
    ignores the event simply never performs the action.
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    type: Literal["approval_required"] = "approval_required"


@dataclass
class Finished:
    """The run ended. `stop_reason` says why."""

    text: str = ""
    stop_reason: Literal["end_turn", "max_steps", "awaiting_approval", "error"] = "end_turn"
    steps: int = 0
    error: str = ""
    type: Literal["finished"] = "finished"


Event = TextDelta | ToolCall | ToolResult | ApprovalRequired | Finished

__all__ = [
    "ApprovalRequired",
    "Event",
    "Finished",
    "TextDelta",
    "ToolCall",
    "ToolResult",
]
