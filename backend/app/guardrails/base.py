"""Base classes for the guardrails system.

Every guardrail check returns a GuardrailResult. Graph nodes inspect the
result's severity to decide how to proceed:
  - PASS:    No issues — continue normally.
  - WARNING: Potential issue detected — continue but log a warning and
             optionally emit a guardrail_warning SSE event.
  - BLOCKED: Hard violation — stop execution and report to the user.

BaseGuardrail is an ABC that all guardrail classes inherit from. It defines
a single check() method that subclasses implement.

GuardrailLogger provides a helper to persist check results to the
guardrail_logs DB table for audit and debugging.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app import database as db

log = logging.getLogger(__name__)


class GuardrailSeverity(str, Enum):
    """Outcome severity of a guardrail check."""
    PASS = "pass"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass
class GuardrailResult:
    """Result of a single guardrail check."""

    check_name: str                         # e.g. "prompt_injection", "rate_limit"
    severity: GuardrailSeverity             # pass / warning / blocked
    message: str = ""                       # Human-readable explanation
    context: dict = field(default_factory=dict)  # Extra data for debugging

    @property
    def passed(self) -> bool:
        return self.severity == GuardrailSeverity.PASS

    @property
    def blocked(self) -> bool:
        return self.severity == GuardrailSeverity.BLOCKED


class BaseGuardrail(ABC):
    """Abstract base class for all guardrails.

    Subclasses implement check() and return a GuardrailResult.
    """

    @abstractmethod
    def check(self, **kwargs: Any) -> GuardrailResult:
        """Run the guardrail check. Returns a GuardrailResult."""
        ...


def log_guardrail_result(
    result: GuardrailResult,
    *,
    workflow_id: str = "",
    session_id: str = "",
    user_id: str = "",
) -> None:
    """Persist a guardrail check result to the guardrail_logs table.

    Only logs warnings and blocks — passes are not stored to keep
    the table manageable.
    """
    if result.passed:
        return

    try:
        import json
        conn = db.get_conn()
        conn.execute(
            """INSERT INTO guardrail_logs
               (id, workflow_id, session_id, user_id, check_name, severity, message, context_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                uuid.uuid4().hex[:8],
                workflow_id,
                session_id,
                user_id,
                result.check_name,
                result.severity.value,
                result.message,
                json.dumps(result.context),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        # Don't let logging failures break the main flow
        log.warning("Failed to log guardrail result: %s", e)
