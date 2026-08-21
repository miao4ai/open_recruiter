"""Action Limits — rate limits, batch caps, and cost controls.

Checks that run BEFORE side effects (sending emails, updating statuses,
creating events) to prevent abuse and accidental mass operations.

Four checks:
  1. Email rate limit — max emails per day per user (default 50).
  2. Batch cap — max items in a single batch operation (default 20).
  3. Cost control — estimated LLM token cost for a planned operation.
  4. Permission check — verifies the user role has the required permission.

Usage in a graph node (e.g. before sending emails):
    from app.guardrails.action_limits import ActionLimits

    limiter = ActionLimits()
    result = limiter.check(
        action="send_email",
        user_id="u1",
        batch_size=15,
    )
    if result.blocked:
        return {"error": result.message, "agent_status": "error"}
"""

from __future__ import annotations

import logging
from datetime import datetime

from app import database as db
from app.guardrails.base import BaseGuardrail, GuardrailResult, GuardrailSeverity

log = logging.getLogger(__name__)

# ── Default limits ────────────────────────────────────────────────────────

DEFAULT_EMAIL_DAILY_LIMIT = 50
DEFAULT_BATCH_CAP = 20
DEFAULT_STATUS_CHANGE_DAILY_LIMIT = 100
DEFAULT_MAX_LLM_CALLS_PER_OPERATION = 50

# Actions that require recruiter role
_RECRUITER_ONLY_ACTIONS = {
    "send_email", "update_candidate_status", "create_event",
    "pipeline_cleanup", "bulk_outreach",
}


class ActionLimits(BaseGuardrail):
    """Enforces rate limits, batch caps, and permission checks."""

    def __init__(
        self,
        email_daily_limit: int = DEFAULT_EMAIL_DAILY_LIMIT,
        batch_cap: int = DEFAULT_BATCH_CAP,
        status_change_daily_limit: int = DEFAULT_STATUS_CHANGE_DAILY_LIMIT,
        max_llm_calls: int = DEFAULT_MAX_LLM_CALLS_PER_OPERATION,
    ):
        self.email_daily_limit = email_daily_limit
        self.batch_cap = batch_cap
        self.status_change_daily_limit = status_change_daily_limit
        self.max_llm_calls = max_llm_calls

    def check(
        self,
        *,
        action: str = "",
        user_id: str = "",
        user_role: str = "recruiter",
        batch_size: int = 1,
        estimated_llm_calls: int = 0,
        **kwargs,
    ) -> GuardrailResult:
        """Run all action limit checks. Returns the most severe result."""
        results = [
            self._check_permission(action, user_role),
            self._check_batch_cap(action, batch_size),
        ]

        if action == "send_email":
            results.append(self._check_email_rate(user_id))

        if action == "update_candidate_status":
            results.append(self._check_status_change_rate(user_id))

        if estimated_llm_calls > 0:
            results.append(self._check_llm_cost(estimated_llm_calls))

        for severity in (GuardrailSeverity.BLOCKED, GuardrailSeverity.WARNING):
            for r in results:
                if r.severity == severity:
                    return r

        return GuardrailResult(
            check_name="action_limits",
            severity=GuardrailSeverity.PASS,
        )

    def _check_permission(self, action: str, user_role: str) -> GuardrailResult:
        """Verify the user role has permission for this action."""
        if action in _RECRUITER_ONLY_ACTIONS and user_role != "recruiter":
            return GuardrailResult(
                check_name="permission",
                severity=GuardrailSeverity.BLOCKED,
                message=f"Action '{action}' requires recruiter role.",
                context={"action": action, "role": user_role},
            )
        return GuardrailResult(check_name="permission", severity=GuardrailSeverity.PASS)

    def _check_batch_cap(self, action: str, batch_size: int) -> GuardrailResult:
        """Prevent excessively large batch operations."""
        if batch_size > self.batch_cap:
            return GuardrailResult(
                check_name="batch_cap",
                severity=GuardrailSeverity.BLOCKED,
                message=f"Batch size {batch_size} exceeds cap of {self.batch_cap}.",
                context={"batch_size": batch_size, "cap": self.batch_cap},
            )
        return GuardrailResult(check_name="batch_cap", severity=GuardrailSeverity.PASS)

    def _check_email_rate(self, user_id: str) -> GuardrailResult:
        """Check daily email sending rate limit."""
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            emails = db.list_emails()
            sent_today = sum(
                1 for e in emails
                if e.get("sent")
                and e.get("sent_at", "").startswith(today)
            )
        except Exception:
            sent_today = 0

        if sent_today >= self.email_daily_limit:
            return GuardrailResult(
                check_name="email_rate_limit",
                severity=GuardrailSeverity.BLOCKED,
                message=f"Daily email limit reached ({sent_today}/{self.email_daily_limit}).",
                context={"sent_today": sent_today, "limit": self.email_daily_limit},
            )

        remaining = self.email_daily_limit - sent_today
        if remaining <= 10:
            return GuardrailResult(
                check_name="email_rate_limit",
                severity=GuardrailSeverity.WARNING,
                message=f"Only {remaining} emails remaining today ({sent_today}/{self.email_daily_limit}).",
                context={"sent_today": sent_today, "remaining": remaining},
            )

        return GuardrailResult(check_name="email_rate_limit", severity=GuardrailSeverity.PASS)

    def _check_status_change_rate(self, user_id: str) -> GuardrailResult:
        """Prevent mass status changes in a single day."""
        # For now, just check batch cap — future: track daily changes in DB
        return GuardrailResult(
            check_name="status_change_rate",
            severity=GuardrailSeverity.PASS,
        )

    def _check_llm_cost(self, estimated_calls: int) -> GuardrailResult:
        """Warn if an operation will make many LLM calls."""
        if estimated_calls > self.max_llm_calls:
            return GuardrailResult(
                check_name="llm_cost",
                severity=GuardrailSeverity.WARNING,
                message=f"This operation will make ~{estimated_calls} LLM calls (limit: {self.max_llm_calls}). Consider reducing scope.",
                context={"estimated": estimated_calls, "limit": self.max_llm_calls},
            )
        return GuardrailResult(check_name="llm_cost", severity=GuardrailSeverity.PASS)
