"""Shared fixtures for the test harness.

Ensures the backend package is importable and provides common test data.
"""

import sys
from pathlib import Path

import pytest

# Make backend/app importable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ── Common test data ──────────────────────────────────────────────────────

@pytest.fixture
def sample_candidate_names() -> list[str]:
    return ["Alice Zhang", "Bob Smith", "Charlie Lee"]


@pytest.fixture
def sample_job_ids() -> list[str]:
    return ["abc12345", "def67890"]
