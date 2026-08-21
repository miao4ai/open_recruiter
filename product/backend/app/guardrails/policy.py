"""Policy Engine — configurable guardrail rules loaded from the settings table.

Instead of hard-coding all limits, the policy engine reads overrides from
the DB settings table. This lets admins tune guardrail behaviour without
code changes (e.g. increase email limits for a high-volume recruiting push).

Supported policy keys (stored in the settings table):
  guardrail_email_daily_limit     — int, default 50
  guardrail_batch_cap             — int, default 20
  guardrail_max_input_length      — int, default 64000
  guardrail_max_llm_calls         — int, default 50
  guardrail_enable_pii_check      — bool, default true
  guardrail_enable_injection_check— bool, default true
  guardrail_enable_safety_check   — bool, default true

Usage:
    from app.guardrails.policy import Policy

    policy = Policy.load()
    limiter = ActionLimits(
        email_daily_limit=policy.email_daily_limit,
        batch_cap=policy.batch_cap,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app import database as db

log = logging.getLogger(__name__)


@dataclass
class Policy:
    """Guardrail policy loaded from the settings table."""

    # Action limits
    email_daily_limit: int = 50
    batch_cap: int = 20
    max_llm_calls: int = 50
    status_change_daily_limit: int = 100

    # Input limits
    max_input_length: int = 64_000

    # Feature toggles
    enable_pii_check: bool = True
    enable_injection_check: bool = True
    enable_safety_check: bool = True

    @classmethod
    def load(cls) -> Policy:
        """Load policy from the DB settings table.

        Missing keys use defaults. Invalid values are silently ignored.
        """
        try:
            settings = db.get_settings()
        except Exception as e:
            log.warning("Failed to load settings for policy, using defaults: %s", e)
            return cls()

        return cls(
            email_daily_limit=_int(settings, "guardrail_email_daily_limit", 50),
            batch_cap=_int(settings, "guardrail_batch_cap", 20),
            max_llm_calls=_int(settings, "guardrail_max_llm_calls", 50),
            status_change_daily_limit=_int(settings, "guardrail_status_change_daily_limit", 100),
            max_input_length=_int(settings, "guardrail_max_input_length", 64_000),
            enable_pii_check=_bool(settings, "guardrail_enable_pii_check", True),
            enable_injection_check=_bool(settings, "guardrail_enable_injection_check", True),
            enable_safety_check=_bool(settings, "guardrail_enable_safety_check", True),
        )


def _int(settings: dict, key: str, default: int) -> int:
    val = settings.get(key, "")
    if not val:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _bool(settings: dict, key: str, default: bool) -> bool:
    val = settings.get(key, "")
    if not val:
        return default
    return val.lower() in ("true", "1", "yes", "on")
