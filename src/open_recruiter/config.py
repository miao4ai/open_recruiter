"""Configuration loading from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    llm_provider: str = "anthropic"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    email_backend: str = "console"
    sendgrid_api_key: str = ""
    email_from: str = "recruiter@example.com"

    db_path: Path = field(default_factory=lambda: Path("open_recruiter.db"))

    def __post_init__(self) -> None:
        if not self.llm_model:
            self.llm_model = {
                "anthropic": "claude-sonnet-4-20250514",
                "openai": "gpt-4o",
            }.get(self.llm_provider, "claude-sonnet-4-20250514")


def load_config(env_file: str | None = None) -> Config:
    """Load configuration from .env file and environment variables."""
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    return Config(
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic"),
        llm_model=os.getenv("LLM_MODEL", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        email_backend=os.getenv("EMAIL_BACKEND", "console"),
        sendgrid_api_key=os.getenv("SENDGRID_API_KEY", ""),
        email_from=os.getenv("EMAIL_FROM", "recruiter@example.com"),
        db_path=Path(os.getenv("DB_PATH", "open_recruiter.db")),
    )
