"""Every module must at least parse and import.

`app/agents/jd.py` shipped a syntax error in every release from v1.0.0 through
v3.0.1. Nothing caught it because the module is imported lazily inside a
``try/except Exception`` at the JD upload call site — ``SyntaxError`` is an
``Exception``, so the failure was swallowed and JD parsing silently returned
nothing for three years of releases.

These tests make that class of bug loud: a module that cannot be parsed or
imported fails here, whether or not anything imports it eagerly at startup.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent.parent / "backend" / "app"


def _python_files() -> list[Path]:
    return sorted(p for p in APP_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _module_names() -> list[str]:
    """Every importable module under app/, including lazily-imported ones."""
    names = ["app"]
    for mod in pkgutil.walk_packages([str(APP_DIR)], prefix="app."):
        names.append(mod.name)
    return sorted(names)


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p.relative_to(APP_DIR)))
def test_module_parses(path: Path) -> None:
    """A module with a syntax error is dead code that fails at the worst moment."""
    source = path.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover - only on failure
        pytest.fail(f"{path.relative_to(APP_DIR)}:{exc.lineno} — {exc.msg}")


@pytest.mark.parametrize("name", _module_names())
def test_module_imports(name: str) -> None:
    """Catches broken imports in modules that are only imported lazily."""
    importlib.import_module(name)


def test_job_description_parsing_is_reachable() -> None:
    """Regression guard for the corruption itself.

    `app/agents/jd.py` was a syntax error through five releases because it was
    only ever imported lazily inside a broad ``except Exception``. Parsing lives
    in the SDK now and the app reaches it through one entry point, so that is
    what has to stay callable.
    """
    from app.sdk_bridge import parse_job, parse_resume

    assert callable(parse_job)
    assert callable(parse_resume)
