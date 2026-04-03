"""Input Validator — checks user input before it reaches the LLM.

Three checks:
  1. Prompt injection detection — scans for common injection patterns
     (role overrides, instruction leaks, jailbreak phrases).
  2. PII scan — detects and flags sensitive data that shouldn't be sent
     to external LLM providers (SSN, credit card numbers, etc.).
  3. Length limits — prevents excessively long inputs that waste tokens
     or could be used for token-stuffing attacks.

Usage in a graph node:
    from app.guardrails.input_validator import InputValidator

    validator = InputValidator()
    result = validator.check(text=user_message)
    if result.blocked:
        return {"error": result.message, "agent_status": "error"}
"""

from __future__ import annotations

import re

from app.guardrails.base import BaseGuardrail, GuardrailResult, GuardrailSeverity

# Max input length in characters (roughly ~16k tokens)
DEFAULT_MAX_LENGTH = 64_000

# ── Prompt injection patterns ─────────────────────────────────────────────
# These catch common attempts to override the system prompt or extract
# instructions. Not exhaustive — a determined attacker can bypass regex —
# but catches the low-hanging fruit and casual attempts.

_INJECTION_PATTERNS = [
    # Direct role override
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.I),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a|an)\s+", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"system\s*prompt\s*:", re.I),
    # Instruction extraction
    re.compile(r"(repeat|show|reveal|print|output)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions)", re.I),
    re.compile(r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions|rules)", re.I),
    # Delimiter injection
    re.compile(r"```\s*system\b", re.I),
    re.compile(r"<\|im_start\|>system", re.I),
    re.compile(r"\[INST\].*\[/INST\]", re.I | re.S),
]

# ── PII patterns ──────────────────────────────────────────────────────────
# Detects common PII formats. These are WARNING-level (not BLOCKED) because
# recruiters legitimately handle candidate contact info. The warning helps
# them be aware before sending to an external LLM.

_PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "passport": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
}


class InputValidator(BaseGuardrail):
    """Validates user input before LLM calls."""

    def __init__(self, max_length: int = DEFAULT_MAX_LENGTH):
        self.max_length = max_length

    def check(self, *, text: str = "", **kwargs) -> GuardrailResult:
        """Run all input checks. Returns the most severe result."""
        results = [
            self._check_length(text),
            self._check_injection(text),
            self._check_pii(text),
        ]

        # Return the most severe result
        for severity in (GuardrailSeverity.BLOCKED, GuardrailSeverity.WARNING):
            for r in results:
                if r.severity == severity:
                    return r

        return GuardrailResult(
            check_name="input_validation",
            severity=GuardrailSeverity.PASS,
        )

    def _check_length(self, text: str) -> GuardrailResult:
        """Block inputs that exceed the character limit."""
        if len(text) > self.max_length:
            return GuardrailResult(
                check_name="input_length",
                severity=GuardrailSeverity.BLOCKED,
                message=f"Input too long ({len(text):,} chars, max {self.max_length:,}).",
                context={"length": len(text), "max": self.max_length},
            )
        return GuardrailResult(check_name="input_length", severity=GuardrailSeverity.PASS)

    def _check_injection(self, text: str) -> GuardrailResult:
        """Detect prompt injection attempts."""
        for pattern in _INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                return GuardrailResult(
                    check_name="prompt_injection",
                    severity=GuardrailSeverity.BLOCKED,
                    message="Potential prompt injection detected.",
                    context={"matched": match.group(0)[:100]},
                )
        return GuardrailResult(check_name="prompt_injection", severity=GuardrailSeverity.PASS)

    def _check_pii(self, text: str) -> GuardrailResult:
        """Detect PII in user input (warning-level)."""
        found = []
        for pii_type, pattern in _PII_PATTERNS.items():
            if pattern.search(text):
                found.append(pii_type)

        if found:
            return GuardrailResult(
                check_name="pii_detection",
                severity=GuardrailSeverity.WARNING,
                message=f"Possible PII detected: {', '.join(found)}. Be cautious with external LLM providers.",
                context={"pii_types": found},
            )
        return GuardrailResult(check_name="pii_detection", severity=GuardrailSeverity.PASS)
