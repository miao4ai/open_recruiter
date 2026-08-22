"""The app runs on the SDK, over its own database.

The point of these tests is that nothing was migrated: `ProductStore` speaks the
SDK's protocol while writing to the same tables the REST endpoints read, so both
paths see the same data.
"""

from __future__ import annotations

import openrecruiter as orc
import pytest

from app import database as db
from app.agent_tools import SEEKER_TOOLS, product_tools, tools_for_role
from app.config import Config
from app.sdk_bridge import ProductStore, build_recruiter, to_sdk_config


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_RECRUITER_DATA_DIR", str(tmp_path))
    import importlib

    importlib.reload(db)
    db.init_db()
    return ProductStore()


def test_product_store_satisfies_the_sdk_protocol(store):
    assert isinstance(store, orc.Store)


def test_a_job_written_through_the_sdk_is_visible_to_the_rest_layer(store):
    job = orc.Job(title="CUDA Engineer", company="Acme", required_skills=["CUDA"], raw_text="jd")
    store.add_job(job)

    assert store.get_job(job.id).title == "CUDA Engineer"
    # The same row, read the way the /api/jobs endpoints read it.
    assert db.get_job(job.id)["title"] == "CUDA Engineer"


def test_a_candidate_round_trips_through_both_layers(store):
    c = orc.Candidate(name="Ada", skills=["CUDA", "NCCL"], experience_years=8)
    store.add_candidate(c)

    loaded = store.get_candidate(c.id)
    assert loaded.name == "Ada"
    assert loaded.skills == ["CUDA", "NCCL"]
    assert db.get_candidate(c.id)["name"] == "Ada"


def test_status_changes_go_through_the_apps_own_update_path(store):
    c = orc.Candidate(name="Ada")
    store.add_candidate(c)

    assert store.set_candidate_status(c.id, orc.CandidateStatus.INTERVIEWING) is True
    assert db.get_candidate(c.id)["status"] == "interviewing"


def test_matches_are_stored_on_the_candidate_jobs_join(store):
    job = orc.Job(title="CUDA Engineer", raw_text="jd")
    cand = orc.Candidate(name="Ada")
    store.add_job(job)
    store.add_candidate(cand)

    store.save_match(
        orc.Match(candidate_id=cand.id, job_id=job.id, score=0.87, strengths=["CUDA"], reasoning="fits")
    )

    row = db.get_candidate_job(cand.id, job.id)
    assert row is not None and row["match_score"] == 0.87
    assert store.list_matches(job.id)[0].score == 0.87


def test_saving_a_match_twice_updates_rather_than_duplicates(store):
    job, cand = orc.Job(raw_text="jd"), orc.Candidate(name="Ada")
    store.add_job(job)
    store.add_candidate(cand)

    for score in (0.2, 0.9):
        store.save_match(orc.Match(candidate_id=cand.id, job_id=job.id, score=score))

    matches = store.list_matches(job.id)
    assert len(matches) == 1
    assert matches[0].score == 0.9


def test_missing_records_return_none_not_a_blank_object(store):
    assert store.get_job("ghost") is None
    assert store.get_candidate("ghost") is None


# ── configuration ────────────────────────────────────────────────────────


def test_the_apps_settings_translate_into_the_sdks():
    sdk = to_sdk_config(
        Config(llm_provider="openai", openai_api_key="k", voyage_api_key="pa-1")
    )
    assert sdk.llm_provider == "openai"
    assert sdk.api_key == "k"
    assert sdk.model_id == "openai/gpt-5.1"


def test_without_an_embedding_key_the_recruiter_still_builds(store):
    r = build_recruiter(Config(anthropic_api_key="test"))
    assert isinstance(r.index, orc.NullVectorIndex)
    assert isinstance(r.store, ProductStore)


# ── tools ────────────────────────────────────────────────────────────────


def test_product_tools_join_the_sdks_own(store):
    r = build_recruiter(Config(anthropic_api_key="test"), extra_tools=product_tools(Config()))

    assert "rank_candidates" in r.tools, "from the SDK"
    assert "check_inbox" in r.tools, "from the app"
    assert "request_resume_upload" in r.tools


def test_upload_tools_return_a_card_rather_than_data():
    tools = {t.name: t for t in product_tools(Config())}

    result = tools["request_resume_upload"](job_id="j1", job_title="CUDA Engineer")
    assert result["ui_card"] == "upload_resume"
    assert result["job_id"] == "j1"


def test_check_inbox_says_so_when_no_mailbox_is_configured():
    tools = {t.name: t for t in product_tools(Config())}
    assert tools["check_inbox"]()["configured"] is False


def test_a_job_seeker_cannot_reach_the_recruiters_pipeline(store):
    """The role check happens before the model sees a schema, not after."""
    r = build_recruiter(Config(anthropic_api_key="test"), extra_tools=product_tools(Config()))

    seeker_tools = tools_for_role(r, "job_seeker")
    names = set(seeker_tools.names())

    assert names <= SEEKER_TOOLS
    assert "list_candidates" not in names
    assert "rank_candidates" not in names
    assert "draft_email" not in names
    assert "search_web_jobs" in names


def test_a_recruiter_keeps_the_full_registry(store):
    r = build_recruiter(Config(anthropic_api_key="test"), extra_tools=product_tools(Config()))
    assert tools_for_role(r, "recruiter") is r.tools


# ── one client, one config ───────────────────────────────────────────────


def test_the_app_and_the_sdk_share_one_vector_client(tmp_path, monkeypatch):
    """Two ChromaDB clients over one directory contend for the same file.

    It used to work only because both happened to register their embedding
    function under the same name. `vectorstore` keeps its API — two dozen call
    sites use it — but it no longer owns a client.
    """
    from app import vectorstore
    from app.config import Config
    from app.routes import settings as settings_route
    from app import sdk_bridge

    sdk_bridge.reset_shared_state()
    cfg = Config(voyage_api_key="pa-test", anthropic_api_key="k")
    monkeypatch.setattr(settings_route, "get_config", lambda: cfg)

    asked = []
    real = sdk_bridge.vector_index
    monkeypatch.setattr(
        sdk_bridge, "vector_index", lambda c: (asked.append(c), real(c))[1]
    )

    vectorstore._get_collection("jobs")
    vectorstore._get_collection("candidates")

    assert len(asked) == 2, "every collection is fetched through the SDK's index"
    assert not hasattr(vectorstore, "_client"), "the module owns no client of its own"
    # ...and the index it went through is the shared one, built once.
    assert real(cfg) is real(cfg)


def test_without_an_embedding_key_the_legacy_helpers_say_so(tmp_path, monkeypatch):
    from app import vectorstore
    from app.config import Config
    from app.routes import settings as settings_route
    from app import sdk_bridge

    sdk_bridge.reset_shared_state()
    monkeypatch.setattr(settings_route, "get_config", lambda: Config())

    with pytest.raises(RuntimeError, match="Voyage API key"):
        vectorstore._get_collection("jobs")


def test_a_key_added_after_startup_takes_effect(tmp_path, monkeypatch):
    """3.0.1 was exactly this bug: the key was captured at launch."""
    from app.config import Config
    from app import sdk_bridge

    sdk_bridge.reset_shared_state()
    cfg = Config(anthropic_api_key="")
    sdk_cfg = sdk_bridge.to_sdk_config(cfg)
    assert sdk_cfg.api_key == ""

    cfg.anthropic_api_key = "sk-ant-added-later"
    assert sdk_bridge.to_sdk_config(cfg) is sdk_cfg, "the same object, refreshed"
    assert sdk_cfg.api_key == "sk-ant-added-later"
