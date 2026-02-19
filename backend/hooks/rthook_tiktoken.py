"""PyInstaller runtime hook for tiktoken.

tiktoken discovers encoding plugins via importlib.metadata entry_points,
which PyInstaller does not preserve. This hook manually registers the
OpenAI encodings (cl100k_base, o200k_base, etc.) before the app runs.
"""

import tiktoken_ext.openai_public as _oai
from tiktoken.registry import ENCODING_CONSTRUCTORS

# Register all encodings exported by tiktoken_ext.openai_public
for _name in dir(_oai):
    _obj = getattr(_oai, _name)
    if callable(_obj) and _name.startswith(("cl100k", "p50k", "r50k", "o200k", "gpt2")):
        ENCODING_CONSTRUCTORS[_name] = _obj
