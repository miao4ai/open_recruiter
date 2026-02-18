"""Configuration management — loads from SQLite settings table + env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ dir first, then fall back to project root
_backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(_backend_dir / ".env")
load_dotenv(_backend_dir.parent / ".env")


@dataclass
class Config:
    llm_provider: str = "anthropic"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    email_backend: str = "console"
    sendgrid_api_key: str = ""
    email_from: str = "recruiter@example.com"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""

    recruiter_name: str = ""
    recruiter_email: str = ""
    recruiter_company: str = ""

    # IMAP (reply detection)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""

    # Slack integration
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_signing_secret: str = ""
    slack_intake_channel: str = ""

    def __post_init__(self) -> None:
        if not self.llm_model:
            self.llm_model = {
                "anthropic": "claude-sonnet-4-20250514",
                "openai": "gpt-5.1",
            }.get(self.llm_provider, "claude-sonnet-4-20250514")


def load_config_from_env() -> Config:
    """Bootstrap config from environment variables (used on first run)."""
    return Config(
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic"),
        llm_model=os.getenv("LLM_MODEL", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        email_backend=os.getenv("EMAIL_BACKEND", "console"),
        sendgrid_api_key=os.getenv("SENDGRID_API_KEY", ""),
        email_from=os.getenv("EMAIL_FROM", "recruiter@example.com"),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        imap_host=os.getenv("IMAP_HOST", ""),
        imap_port=int(os.getenv("IMAP_PORT", "993")),
        imap_username=os.getenv("IMAP_USERNAME", ""),
        imap_password=os.getenv("IMAP_PASSWORD", ""),
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
        slack_app_token=os.getenv("SLACK_APP_TOKEN", ""),
        slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET", ""),
        slack_intake_channel=os.getenv("SLACK_INTAKE_CHANNEL", ""),
    )
