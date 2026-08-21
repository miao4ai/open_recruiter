"""Guardrails — validation layer for LangGraph nodes.

Three categories of checks:
  - Input:  prompt injection detection, PII scan, length limits
  - Output: content safety, hallucination checks, format validation
  - Action: rate limits, batch caps, cost controls, permission checks

Guardrails are applied as decorators or called directly by graph nodes.
All checks return a GuardrailResult; the node decides whether to proceed,
warn, or block based on severity.
"""

from app.guardrails.base import GuardrailResult, GuardrailSeverity

__all__ = ["GuardrailResult", "GuardrailSeverity"]
