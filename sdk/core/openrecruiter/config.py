"""Runtime configuration for the SDK.

Nothing here reads a database or a settings UI — a host application decides
where values come from and passes a `Config` in. Environment variables are read
only as a convenience for scripts and notebooks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Provider defaults. Model ids move; override them rather than editing here.
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5.1",
}

DEFAULT_PROVIDER = "anthropic"
DEFAULT_EMBED_MODEL = "voyage-4-lite"


@dataclass
class Config:
    llm_provider: str = DEFAULT_PROVIDER
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Embeddings are an API call, never a local model — see the vector store.
    voyage_api_key: str = ""
    voyage_model: str = DEFAULT_EMBED_MODEL

    max_tokens: int = 4096

    def __post_init__(self) -> None:
        if not self.llm_model:
            self.llm_model = DEFAULT_MODELS.get(self.llm_provider, DEFAULT_MODELS[DEFAULT_PROVIDER])

    @property
    def api_key(self) -> str:
        return {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
        }.get(self.llm_provider, "")

    @property
    def model_id(self) -> str:
        """The provider-qualified model string LiteLLM expects."""
        if "/" in self.llm_model:
            return self.llm_model
        return f"{self.llm_provider}/{self.llm_model}"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER),
            llm_model=os.getenv("LLM_MODEL", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            voyage_api_key=os.getenv("VOYAGE_API_KEY", ""),
            voyage_model=os.getenv("VOYAGE_MODEL", DEFAULT_EMBED_MODEL),
        )


__all__ = ["Config", "DEFAULT_MODELS", "DEFAULT_PROVIDER", "DEFAULT_EMBED_MODEL"]
