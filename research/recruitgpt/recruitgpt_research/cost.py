"""Measuring what generation costs, while it is being spent.

Estimating token counts is how a budget gets away from you. Every call records
the usage the provider actually reported, tagged with the stage that made it, so
the report says *where* the money went rather than only how much — which is the
part that decides what to change before scaling up.

Prices are configuration, not constants. They change, and a run from three
months ago has to remain explicable, so the table used is written into the run
manifest alongside the totals.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class BudgetExceeded(RuntimeError):
    """Raised at a safe boundary once the cap is reached.

    Carries what was spent so the caller can report it rather than only fail.
    """

    def __init__(self, spent: float, limit: float) -> None:
        super().__init__(f"Budget exhausted: ${spent:.2f} of ${limit:.2f}")
        self.spent = spent
        self.limit = limit


@dataclass(frozen=True)
class Price:
    """US dollars per million tokens."""

    input: float
    output: float
    #: Providers bill cached input at a discount. Counted separately or the
    #: report credits caching to the wrong stage.
    cached_input: float = 0.0


@dataclass
class Call:
    stage: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0

    def cost(self, price: Price) -> float:
        fresh = max(0, self.input_tokens - self.cached_tokens)
        return (
            fresh * price.input
            + self.cached_tokens * price.cached_input
            + self.output_tokens * price.output
        ) / 1_000_000


@dataclass
class StageTotal:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost: float = 0.0


@dataclass
class CostMeter:
    """Records every call, and stops the run when the cap is reached."""

    prices: dict[str, Price]
    budget_usd: float | None = None
    calls: list[Call] = field(default_factory=list)

    def record(
        self,
        stage: str,
        model: str,
        usage: Any,
        *,
        check_budget: bool = False,
    ) -> Call:
        """Log one call from a provider response.

        `usage` is whatever the client returned — a LiteLLM usage object, an
        SDK object, or a plain dict. The counts are read from it rather than
        recomputed, because a tokenizer disagreeing with the provider by a few
        percent compounds over a hundred thousand calls.
        """
        call = Call(
            stage=stage,
            model=model,
            input_tokens=_field(usage, "prompt_tokens", "input_tokens"),
            output_tokens=_field(usage, "completion_tokens", "output_tokens"),
            cached_tokens=_field(usage, "cache_read_input_tokens", "cached_tokens"),
        )
        self.calls.append(call)
        if check_budget:
            self.check()
        return call

    # ── budget ───────────────────────────────────────────────────────────

    @property
    def spent(self) -> float:
        return sum(call.cost(self._price(call.model)) for call in self.calls)

    def check(self) -> None:
        """Raise if the cap is reached. Call between examples, never mid-example.

        Stopping inside an example leaves a half-generated record that looks
        complete, which is worse than stopping one example early.
        """
        if self.budget_usd is not None and self.spent >= self.budget_usd:
            raise BudgetExceeded(self.spent, self.budget_usd)

    def remaining(self) -> float | None:
        return None if self.budget_usd is None else max(0.0, self.budget_usd - self.spent)

    def _price(self, model: str) -> Price:
        if model not in self.prices:
            raise KeyError(
                f"No price for {model!r}. Add it to the price table rather than "
                "letting a run report a cost that excludes one of its models."
            )
        return self.prices[model]

    # ── reporting ────────────────────────────────────────────────────────

    def by_stage(self) -> dict[str, StageTotal]:
        totals: dict[str, StageTotal] = defaultdict(StageTotal)
        for call in self.calls:
            total = totals[call.stage]
            total.calls += 1
            total.input_tokens += call.input_tokens
            total.output_tokens += call.output_tokens
            total.cached_tokens += call.cached_tokens
            total.cost += call.cost(self._price(call.model))
        return dict(totals)

    def report(self, examples: int, scale_to: int | None = None) -> dict:
        """The artefact phase 1 exists to produce.

        Per-example cost broken down by stage, and what the full target would
        come to — the number that decides how large the real dataset should be.
        """
        stages = {name: asdict(total) for name, total in self.by_stage().items()}
        for total in stages.values():
            total["cost"] = round(total["cost"], 4)
            total["cost_per_example"] = round(total["cost"] / examples, 6) if examples else 0.0

        spent = self.spent
        report = {
            "examples": examples,
            "total_cost_usd": round(spent, 4),
            "cost_per_example_usd": round(spent / examples, 6) if examples else 0.0,
            "by_stage": dict(sorted(stages.items(), key=lambda kv: -kv[1]["cost"])),
            "prices_used": {m: asdict(p) for m, p in self.prices.items()},
        }
        if scale_to:
            report["extrapolation"] = {
                "examples": scale_to,
                "estimated_usd": round(spent / examples * scale_to, 2) if examples else 0.0,
                "note": (
                    "Linear in examples. Real generation grows superlinearly if the "
                    "shortlist grows, since a teacher call carries every candidate."
                ),
            }
        return report

    def write(self, path: str | Path, examples: int, scale_to: int | None = None) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.report(examples, scale_to), indent=2))
        return path


def _field(usage: Any, *names: str) -> int:
    """Read a count from a usage object or dict, whatever it calls it."""
    for name in names:
        if isinstance(usage, dict):
            if usage.get(name) is not None:
                return int(usage[name])
        elif getattr(usage, name, None) is not None:
            return int(getattr(usage, name))
    return 0


__all__ = ["BudgetExceeded", "Call", "CostMeter", "Price", "StageTotal"]
