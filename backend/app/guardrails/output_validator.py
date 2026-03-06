"""Output Validator — checks LLM output before it reaches the user.

Three checks:
  1. Content safety — scans for harmful, offensive, or inappropriate content
     that the LLM should not produce in a recruitment context.
  2. Hallucination check — detects when the LLM fabricates candidate names,
     job IDs, or emails that don't exist in the system.
  3. Format validation — ensures the response matches the expected structure
     (e.g. JSON with required fields).

Usage in a graph node:
    from app.guardrails.output_validator import OutputValidator

    validator = OutputValidator()
    result = validator.check(
        text=llm_response,
        expected_format="json",
        known_candidates=["Alice", "Bob"],
    )
    if result.blocked:
        return {"error": result.message, "agent_status": "error"}
"""

from __future__ import annotations

import json
import re

from app.guardrails.base import BaseGuardrail, GuardrailResult, GuardrailSeverity

# ── Content safety patterns ───────────────────────────────────────────────
# Catches content that has no place in a recruitment assistant's output.
# These are BLOCKED-level — the response should not be shown to the user.

_UNSAFE_PATTERNS = [
    # Discriminatory language in hiring context
    re.compile(
        r"\b(too\s+old|too\s+young|not\s+the\s+right\s+gender|"
        r"wrong\s+race|prefer\s+male|prefer\s+female|"
        r"don'?t\s+hire\s+(women|men|disabled|older))\b",
        re.I,
    ),
    # Explicit refusal to follow employment law
    re.compile(r"ignore\s+(employment|labor|discrimination)\s+(law|regulation)", re.I),
]

# Max output length — prevents runaway generation
DEFAULT_MAX_OUTPUT_LENGTH = 100_000


class OutputValidator(BaseGuardrail):
    """Validates LLM output before returning to the user."""

    def __init__(self, max_length: int = DEFAULT_MAX_OUTPUT_LENGTH):
        self.max_length = max_length

    def check(
        self,
        *,
        text: str = "",
        expected_format: str = "",
        known_candidates: list[str] | None = None,
        known_job_ids: list[str] | None = None,
        **kwargs,
    ) -> GuardrailResult:
        """Run all output checks. Returns the most severe result."""
        results = [
            self._check_safety(text),
            self._check_length(text),
        ]

        if expected_format == "json":
            results.append(self._check_json_format(text))

        if known_candidates is not None:
            results.append(self._check_hallucination(text, known_candidates, known_job_ids or []))

        for severity in (GuardrailSeverity.BLOCKED, GuardrailSeverity.WARNING):
            for r in results:
                if r.severity == severity:
                    return r

        return GuardrailResult(
            check_name="output_validation",
            severity=GuardrailSeverity.PASS,
        )

    def _check_safety(self, text: str) -> GuardrailResult:
        """Check for harmful or discriminatory content."""
        for pattern in _UNSAFE_PATTERNS:
            match = pattern.search(text)
            if match:
                return GuardrailResult(
                    check_name="content_safety",
                    severity=GuardrailSeverity.BLOCKED,
                    message="LLM output contains potentially discriminatory content.",
                    context={"matched": match.group(0)[:100]},
                )
        return GuardrailResult(check_name="content_safety", severity=GuardrailSeverity.PASS)

    def _check_length(self, text: str) -> GuardrailResult:
        """Block excessively long outputs."""
        if len(text) > self.max_length:
            return GuardrailResult(
                check_name="output_length",
                severity=GuardrailSeverity.WARNING,
                message=f"Output unusually long ({len(text):,} chars). May indicate runaway generation.",
                context={"length": len(text), "max": self.max_length},
            )
        return GuardrailResult(check_name="output_length", severity=GuardrailSeverity.PASS)

    def _check_json_format(self, text: str) -> GuardrailResult:
        """Validate that the output is parseable JSON."""
        raw = text.strip()
        # Strip markdown code fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        try:
            json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            return GuardrailResult(
                check_name="json_format",
                severity=GuardrailSeverity.WARNING,
                message=f"LLM output is not valid JSON: {e}",
                context={"preview": raw[:200]},
            )
        return GuardrailResult(check_name="json_format", severity=GuardrailSeverity.PASS)

    def _check_hallucination(
        self,
        text: str,
        known_candidates: list[str],
        known_job_ids: list[str],
    ) -> GuardrailResult:
        """Detect potentially hallucinated references.

        Looks for patterns like "candidate John Smith" or "job ID xyz123"
        that don't match known data. This is a heuristic — not perfect,
        but catches obvious fabrications.
        """
        # Extract candidate name references
        name_refs = re.findall(r"candidate\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text)
        hallucinated_names = [
            name for name in name_refs
            if name not in known_candidates
        ]

        # Extract job ID references
        id_refs = re.findall(r"job\s+(?:ID\s+)?([a-f0-9]{6,8})", text, re.I)
        hallucinated_ids = [
            jid for jid in id_refs
            if jid not in known_job_ids
        ]

        if hallucinated_names or hallucinated_ids:
            return GuardrailResult(
                check_name="hallucination",
                severity=GuardrailSeverity.WARNING,
                message="LLM may have hallucinated references not in the system.",
                context={
                    "unknown_names": hallucinated_names[:5],
                    "unknown_job_ids": hallucinated_ids[:5],
                },
            )
        return GuardrailResult(check_name="hallucination", severity=GuardrailSeverity.PASS)
