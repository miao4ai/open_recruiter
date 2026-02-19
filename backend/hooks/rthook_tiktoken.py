"""PyInstaller runtime hook for tiktoken.

tiktoken discovers encoding plugins via importlib.metadata entry_points,
which PyInstaller does not preserve. This hook manually registers the
OpenAI encodings (cl100k_base, o200k_base, etc.) before the app runs.
"""

import tiktoken_ext.openai_public as _ext
import tiktoken.registry as _reg

# Collect all encoding constructor functions from the extension module
_constructors = {}
for _name in dir(_ext):
    if _name.startswith("_"):
        continue
    _obj = getattr(_ext, _name)
    if callable(_obj):
        _constructors[_name] = _obj

# Register into tiktoken's internal registry (handle different versions)
for _attr in (
    "ENCODING_CONSTRUCTORS",
    "_ENCODING_CONSTRUCTORS",
    "_CONSTRUCTORS",
):
    _registry = getattr(_reg, _attr, None)
    if isinstance(_registry, dict):
        _registry.update(_constructors)
        break
else:
    # Fallback: monkey-patch _find_constructors to return our constructors
    _orig = getattr(_reg, "_find_constructors", None)

    def _patched_find():
        result = {}
        if _orig:
            try:
                result = _orig()
            except Exception:
                pass
        result.update(_constructors)
        return result

    _reg._find_constructors = _patched_find
