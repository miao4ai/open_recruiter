"""Model providers: chat over a hosted API, embeddings over whichever backend
the host picked — including, if it asks for one, a local model.
"""

from openrecruiter.providers.llm import LLM, LLMError

__all__ = ["LLM", "LLMError"]
