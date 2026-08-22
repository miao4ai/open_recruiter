"""Tools the model can call, and the registry that holds them.

A tool is a plain function plus a JSON schema. The registry turns a set of them
into what a provider expects and dispatches calls back. Hosts register their own
alongside the built-in ones — that is how the desktop app adds `upload_resume`
or `check_inbox` without those concerns leaking into the SDK.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class Tool:
    """One callable exposed to the model."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    fn: Callable[..., Any] = field(default=lambda: None, repr=False)

    #: Actions that reach outside the system — sending mail, bulk edits — set
    #: this. The agent stops and emits `ApprovalRequired` instead of running it.
    requires_approval: bool = False

    def schema(self) -> dict[str, Any]:
        """The provider-facing description of this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __call__(self, **kwargs: Any) -> Any:
        return self.fn(**kwargs)


class ToolError(RuntimeError):
    """A tool was called wrongly — unknown name, or bad arguments."""


class ToolRegistry:
    """A named set of tools."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    # ── registration ─────────────────────────────────────────────────────

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ToolError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        return tool

    def extend(self, tools: list[Tool]) -> "ToolRegistry":
        for tool in tools:
            self.register(tool)
        return self

    # ── access ───────────────────────────────────────────────────────────

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise ToolError(f"Unknown tool '{name}'") from None

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    # ── dispatch ─────────────────────────────────────────────────────────

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Run a tool.

        Unexpected keys are dropped rather than raising: models routinely invent
        a plausible extra argument, and losing a whole turn to that is worse
        than ignoring it. Missing *required* arguments still raise, because
        those change what the call means.
        """
        tool = self.get(name)
        args = dict(arguments or {})

        try:
            sig = inspect.signature(tool.fn)
        except (TypeError, ValueError):  # builtins and C callables
            return tool.fn(**args)

        accepts_kwargs = any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        if not accepts_kwargs:
            unexpected = set(args) - set(sig.parameters)
            if unexpected:
                log.info("Tool %s: ignoring unexpected arguments %s", name, sorted(unexpected))
                args = {k: v for k, v in args.items() if k in sig.parameters}

        missing = [
            pname
            for pname, p in sig.parameters.items()
            if p.default is inspect.Parameter.empty
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            and pname not in args
        ]
        if missing:
            raise ToolError(f"Tool '{name}' is missing required arguments: {', '.join(missing)}")

        return tool.fn(**args)


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    requires_approval: bool = False,
) -> Callable[[Callable[..., Any]], Tool]:
    """Decorator form: turn a function into a `Tool`."""

    def decorate(fn: Callable[..., Any]) -> Tool:
        return Tool(
            name=name,
            description=description,
            parameters=parameters or {"type": "object", "properties": {}},
            fn=fn,
            requires_approval=requires_approval,
        )

    return decorate


__all__ = ["Tool", "ToolError", "ToolRegistry", "tool"]
