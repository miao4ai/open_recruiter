"""Memory harness — 4-tier memory system (sensory / working / long-term / entity).

Run:  cd backend && uv run python -m pytest ../tests/harness/test_memory.py -v
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# Fixture: isolated SQLite DB per test
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point app.database at a tmp SQLite file and run init_db()."""
    from app import database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    yield db


# ═══════════════════════════════════════════════════════════════════════════
# 1. Sensory memory — in-process ring buffer
# ═══════════════════════════════════════════════════════════════════════════

class TestSensoryMemory:
    def setup_method(self):
        from app.memory import sensory
        sensory._BUFFER.clear("u1")
        sensory._BUFFER.clear("u2")

    def test_emit_and_recent(self):
        from app.memory import emit_event, recent_events
        emit_event("u1", "upload_resume", "uploaded Alice.pdf")
        events = recent_events("u1")
        assert len(events) == 1
        assert events[0].kind == "upload_resume"
        assert events[0].summary == "uploaded Alice.pdf"

    def test_per_user_isolation(self):
        from app.memory import emit_event, recent_events
        emit_event("u1", "view_candidate", "Alice")
        emit_event("u2", "view_candidate", "Bob")
        assert len(recent_events("u1")) == 1
        assert len(recent_events("u2")) == 1
        assert recent_events("u1")[0].summary == "Alice"

    def test_ring_buffer_caps_at_10(self):
        from app.memory import emit_event, recent_events
        for i in range(15):
            emit_event("u1", "event", f"#{i}")
        events = recent_events("u1", limit=20)
        # Ring buffer capped at 10 — oldest 5 dropped
        assert len(events) == 10
        assert events[-1].summary == "#14"
        assert events[0].summary == "#5"

    def test_recent_limit_param(self):
        from app.memory import emit_event, recent_events
        for i in range(5):
            emit_event("u1", "k", f"e{i}")
        assert len(recent_events("u1", limit=3)) == 3

    def test_empty_user(self):
        from app.memory import recent_events
        assert recent_events("nobody") == []

    def test_blank_user_id_ignored(self):
        from app.memory import emit_event, recent_events
        emit_event("", "kind", "summary")
        assert recent_events("") == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. Working memory — session_state table
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkingMemory:

    def test_returns_none_for_unknown_session(self, isolated_db):
        from app.memory import get_working_memory
        assert get_working_memory("ghost") is None

    def test_create_and_read_back(self, isolated_db):
        from app.memory import get_working_memory, update_working_memory
        update_working_memory("s1", "u1", current_goal="Fill Senior Backend in 2 weeks")
        state = get_working_memory("s1")
        assert state is not None
        assert state["current_goal"] == "Fill Senior Backend in 2 weeks"
        assert state["open_workflows"] == []
        assert state["focused_entities"] == []

    def test_update_merges(self, isolated_db):
        from app.memory import update_working_memory, get_working_memory
        update_working_memory("s1", "u1", current_goal="goal A")
        update_working_memory("s1", "u1", scratchpad="some notes")
        state = get_working_memory("s1")
        assert state["current_goal"] == "goal A"
        assert state["scratchpad"] == "some notes"

    def test_focused_entity_dedup(self, isolated_db):
        from app.memory.working import add_focused_entity, get_working_memory
        add_focused_entity("s1", "u1", "candidate", "c1", "Alice")
        add_focused_entity("s1", "u1", "candidate", "c1", "Alice")  # duplicate
        add_focused_entity("s1", "u1", "candidate", "c2", "Bob")
        state = get_working_memory("s1")
        ids = [f["entity_id"] for f in state["focused_entities"]]
        assert ids == ["c1", "c2"]


# ═══════════════════════════════════════════════════════════════════════════
# 3. Entity memory — entity_memory table
# ═══════════════════════════════════════════════════════════════════════════

class TestEntityMemory:

    def test_first_interaction_creates_row(self, isolated_db):
        from app.memory import update_entity_after_action
        update_entity_after_action(
            "u1", "candidate", "c1", "compose_email",
            summary_hint="drafted email to Alice",
        )
        row = isolated_db.get_entity_memory("u1", "candidate", "c1")
        assert row is not None
        assert row["interaction_count"] == 1
        assert row["summary"] == "drafted email to Alice"
        assert row["last_interaction_at"] is not None

    def test_subsequent_actions_bump_count(self, isolated_db):
        from app.memory import update_entity_after_action
        for action in ["compose_email", "evaluate_candidate", "match_candidate"]:
            update_entity_after_action("u1", "candidate", "c1", action, summary_hint=action)
        row = isolated_db.get_entity_memory("u1", "candidate", "c1")
        assert row["interaction_count"] == 3
        # Summary should reflect the most recent action
        assert row["summary"] == "match_candidate"

    def test_relations_dedup(self, isolated_db):
        from app.memory import update_entity_after_action
        update_entity_after_action(
            "u1", "candidate", "c1", "compose_email",
            relations=["referred_by:Bob", "applied_to:job_42"],
        )
        update_entity_after_action(
            "u1", "candidate", "c1", "evaluate_candidate",
            relations=["referred_by:Bob", "applied_to:job_99"],  # Bob dup, job_99 new
        )
        row = isolated_db.get_entity_memory("u1", "candidate", "c1")
        assert sorted(row["relations"]) == sorted(["referred_by:Bob", "applied_to:job_42", "applied_to:job_99"])

    def test_traits_merge(self, isolated_db):
        from app.memory import update_entity_after_action
        update_entity_after_action("u1", "candidate", "c1", "evaluate_candidate", traits={"score": 85})
        update_entity_after_action("u1", "candidate", "c1", "match_candidate", traits={"top_match": "Senior ML"})
        row = isolated_db.get_entity_memory("u1", "candidate", "c1")
        assert row["traits"] == {"score": 85, "top_match": "Senior ML"}

    def test_per_user_isolation(self, isolated_db):
        from app.memory import update_entity_after_action
        update_entity_after_action("u1", "candidate", "c1", "x", summary_hint="u1 summary")
        update_entity_after_action("u2", "candidate", "c1", "y", summary_hint="u2 summary")
        assert isolated_db.get_entity_memory("u1", "candidate", "c1")["summary"] == "u1 summary"
        assert isolated_db.get_entity_memory("u2", "candidate", "c1")["summary"] == "u2 summary"

    def test_entity_resolution_from_message(self, isolated_db):
        from app.memory import update_entity_after_action
        from app.memory.entity import get_entities_for_message
        update_entity_after_action("u1", "candidate", "c1", "x", summary_hint="known candidate")

        candidates_in_context = [
            {"id": "c1", "name": "Alice Zhang"},
            {"id": "c2", "name": "Bob Smith"},
        ]
        # Alice IS in context; Charlie Brown is NOT
        hits = get_entities_for_message(
            "u1", "let's discuss Alice Zhang and Charlie Brown", candidates_in_context,
        )
        assert len(hits) == 1
        assert hits[0]["entity_id"] == "c1"

    def test_entity_resolution_with_no_message_matches(self, isolated_db):
        from app.memory.entity import get_entities_for_message
        candidates_in_context = [{"id": "c1", "name": "Alice Zhang"}]
        hits = get_entities_for_message("u1", "just chatting about jobs", candidates_in_context)
        assert hits == []


# ═══════════════════════════════════════════════════════════════════════════
# 4. Loader — 4-layer context builder
# ═══════════════════════════════════════════════════════════════════════════

class TestLoader:

    def setup_method(self):
        from app.memory import sensory
        sensory._BUFFER.clear("u1")

    def test_empty_state_returns_empty_string(self, isolated_db):
        from app.memory import build_memory_context
        block = build_memory_context("u1", "s1", "hello", candidates_in_context=[])
        assert block == ""

    def test_sensory_only(self, isolated_db):
        from app.memory import build_memory_context, emit_event
        emit_event("u1", "upload_resume", "uploaded Alice.pdf")
        block = build_memory_context("u1", "s1", "hi", candidates_in_context=[])
        assert "## Agent Memory" in block
        assert "### Sensory" in block
        assert "upload_resume" in block
        assert "uploaded Alice.pdf" in block

    def test_working_only(self, isolated_db):
        from app.memory import build_memory_context, update_working_memory
        update_working_memory("s1", "u1", current_goal="hire SRE this quarter")
        block = build_memory_context("u1", "s1", "hi", candidates_in_context=[])
        assert "### Working" in block
        assert "hire SRE this quarter" in block

    def test_long_term_loads_existing_memories(self, isolated_db):
        from app.memory import build_memory_context
        now = datetime.now().isoformat()
        isolated_db.insert_memory({
            "id": "m1", "user_id": "u1", "memory_type": "explicit",
            "category": "tone", "content": "prefer concise emails",
            "source": "chat", "confidence": 1.0, "access_count": 0,
            "created_at": now, "updated_at": now,
        })
        block = build_memory_context("u1", "s1", "hi", candidates_in_context=[])
        assert "### Long-term" in block
        assert "[preference]" in block
        assert "prefer concise emails" in block

    def test_entity_layer(self, isolated_db):
        from app.memory import build_memory_context, update_entity_after_action
        update_entity_after_action("u1", "candidate", "c1", "evaluate_candidate", summary_hint="strong on ML")
        candidates = [{"id": "c1", "name": "Alice Zhang"}]
        block = build_memory_context("u1", "s1", "tell me about Alice Zhang", candidates_in_context=candidates)
        assert "### Entity" in block
        assert "strong on ML" in block

    def test_all_layers_combine(self, isolated_db):
        from app.memory import (
            build_memory_context, emit_event,
            update_working_memory, update_entity_after_action,
        )
        now = datetime.now().isoformat()

        emit_event("u1", "upload_resume", "Alice.pdf")
        update_working_memory("s1", "u1", current_goal="hire SRE")
        isolated_db.insert_memory({
            "id": "m1", "user_id": "u1", "memory_type": "implicit",
            "category": "candidate_preference", "content": "leans toward backend",
            "source": "activity", "confidence": 0.8, "access_count": 0,
            "created_at": now, "updated_at": now,
        })
        update_entity_after_action("u1", "candidate", "c1", "evaluate_candidate", summary_hint="strong on ML")

        block = build_memory_context(
            "u1", "s1", "what about Alice Zhang?",
            candidates_in_context=[{"id": "c1", "name": "Alice Zhang"}],
        )

        # All four section headers present
        assert "### Sensory" in block
        assert "### Working" in block
        assert "### Long-term" in block
        assert "### Entity" in block
        # And they appear in the right order
        assert block.index("### Sensory") < block.index("### Working")
        assert block.index("### Working") < block.index("### Long-term")
        assert block.index("### Long-term") < block.index("### Entity")
