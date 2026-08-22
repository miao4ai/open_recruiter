"""Tool results become the exact shapes the chat UI reads.

These are the parity tests for retiring the legacy `_process_actions` handlers.
Each assertion names the field the front end actually indexes into, because a
block with the right `type` and the wrong keys renders as an empty card and
nobody notices until a user does.
"""

from __future__ import annotations

import pytest

from app.blocks import as_action, as_block, as_context_hint


# ── actions (singular: one per message) ──────────────────────────────────


def test_a_ui_card_becomes_an_action_without_its_note():
    """The note is written for the model, not for the renderer."""
    action = as_action(
        "request_resume_upload",
        {"ui_card": "upload_resume", "job_id": "j1", "job_title": "CUDA", "note": "panel open"},
    )
    assert action == {"type": "upload_resume", "job_id": "j1", "job_title": "CUDA"}


def test_create_job_and_create_candidate_nest_under_their_own_key():
    # Chat.tsx reads msg.action.job / msg.action.candidate
    assert as_action("create_job", {"id": "j1", "title": "CUDA"})["job"]["id"] == "j1"
    assert as_action("create_candidate", {"id": "c1", "name": "Ada"})["candidate"]["name"] == "Ada"


@pytest.mark.parametrize("tool", ["draft_email", "recommend_to_employer"])
def test_both_drafting_tools_produce_a_compose_email_action(tool):
    action = as_action(tool, {"subject": "Hello", "body": "Hi Ada,"})

    assert action["type"] == "compose_email"
    assert action["email"]["subject"] == "Hello"  # msg.action.email


def test_an_empty_draft_is_not_offered_as_a_card():
    assert as_action("draft_email", {"subject": "", "body": ""}) is None


def test_market_analysis_nests_under_report():
    action = as_action("market_analysis", {"summary": "Tight market", "salary_range": "$200k+"})
    assert action["report"]["salary_range"] == "$200k+"  # msg.action.report


def test_a_tool_with_no_card_produces_no_action():
    assert as_action("list_jobs", [{"id": "j1"}]) is None
    assert as_action("set_candidate_status", {"updated": True}) is None


# ── blocks (a list: several per message) ─────────────────────────────────


def test_ranked_candidates_fill_the_match_report_card():
    block = as_block(
        "rank_candidates",
        [
            {
                "candidate_id": "c1",
                "name": "Ada",
                "current_title": "ML Systems Engineer",
                "current_company": "Acme",
                "score": 0.91,
                "strengths": ["CUDA at scale"],
                "gaps": [],
                "reasoning": "Direct match.",
                "skills": ["CUDA"],
                "experience_years": 8,
            }
        ],
    )

    assert block["type"] == "match_report"
    ranking = block["rankings"][0]
    assert ranking["candidate_name"] == "Ada"
    assert ranking["company"] == "ML Systems Engineer @ Acme"
    assert ranking["score"] == 0.91
    assert ranking["one_liner"] == "Direct match."
    assert ranking["job_id"] == "c1", "the card navigates by this field"


def test_a_ranking_without_a_reason_still_gets_a_one_liner():
    block = as_block(
        "rank_candidates",
        [{"candidate_id": "c1", "name": "Ada", "experience_years": 8, "skills": ["CUDA", "NCCL"]}],
    )
    assert block["rankings"][0]["one_liner"] == "8 yrs · CUDA, NCCL"


def test_an_empty_ranking_produces_no_card():
    assert as_block("rank_candidates", []) is None


def test_the_evaluation_swarm_fills_the_candidate_eval_card():
    block = as_block(
        "evaluate_candidate",
        {
            "candidate": {"id": "c1", "name": "Ada", "current_title": "ML Systems"},
            "job_title": "CUDA Engineer",
            "job_company": "Acme",
            "dimensions": [{"name": "skills", "score": 90}],
            "overall_score": 87,
            "hire_recommendation": "yes",
            "synthesis": "Strong systems background.",
        },
    )

    assert block["type"] == "candidate_eval"
    assert block["overall_score"] == 87
    assert block["hire_recommendation"] == "yes"
    assert block["dimensions"][0]["name"] == "skills"


def test_a_failed_evaluation_produces_no_card():
    assert as_block("evaluate_candidate", {"error": "Candidate not found"}) is None


def test_the_inbox_card_gets_the_counts_it_displays():
    block = as_block(
        "check_inbox",
        {
            "configured": True,
            "count": 2,
            "messages": [{"from": "a@x.com", "unread": True}, {"from": "b@x.com"}],
        },
    )

    assert block["type"] == "inbox_preview"
    assert block["total"] == 2
    assert block["unread"] == 1, "the card shows an unread badge"


def test_an_unconfigured_mailbox_produces_no_card():
    assert as_block("check_inbox", {"configured": False}) is None


def test_web_search_results_keep_their_index_for_follow_ups():
    """"analyse the second one" only works if the numbering survives."""
    block = as_block("search_web_jobs", [{"index": 1, "title": "CUDA Engineer", "url": "http://x"}])

    assert block["type"] == "job_search_results"
    assert block["jobs"][0]["index"] == 1


def test_a_job_match_analysis_keeps_the_job_and_the_verdict_apart():
    block = as_block(
        "analyze_job_match",
        {
            "job": {"title": "CUDA Engineer", "company": "Acme", "url": "http://x"},
            "match": {"score": 0.8, "strengths": ["CUDA"], "gaps": ["No Triton"]},
        },
    )

    assert block["type"] == "job_match_result"
    assert block["job"]["company"] == "Acme"
    assert block["match"]["gaps"] == ["No Triton"]


def test_resume_suggestions_fill_the_improvement_card():
    block = as_block(
        "improve_resume",
        {
            "summary": "Lead with the distributed work.",
            "suggestions": [{"area": "skills", "issue": "buried", "action": "move up", "priority": "high"}],
            "job_title": "CUDA Engineer",
            "job_company": "Acme",
        },
    )

    assert block["type"] == "resume_improvement"
    assert block["suggestions"][0]["priority"] == "high"
    assert block["match_score"] == 0.0, "absent rather than missing — the card reads it"


def test_a_cover_letter_card_needs_a_body():
    assert as_block("generate_cover_letter", {"subject": "s", "body": ""}) is None
    block = as_block("generate_cover_letter", {"job_title": "CUDA", "subject": "s", "body": "Dear..."})
    assert block["type"] == "cover_letter"
    assert block["body"] == "Dear..."


def test_tools_with_no_card_produce_no_block():
    assert as_block("list_jobs", [{"id": "j1"}]) is None
    assert as_block("set_candidate_status", {"updated": True}) is None
    assert as_block("rank_candidates", None) is None


def test_every_block_type_produced_is_one_the_ui_renders():
    """The union in types/index.ts, checked against what this module emits."""
    rendered = {
        "match_report", "candidate_eval", "inbox_preview", "job_search_results",
        "job_match_result", "resume_improvement", "cover_letter",
        "approval_block", "scheduling_approval", "pipeline_cleanup",
        "bulk_outreach", "plan_preview", "guardrail_warning",
    }
    produced = {
        as_block("rank_candidates", [{"candidate_id": "c1"}])["type"],
        as_block("evaluate_candidate", {"dimensions": [], "overall_score": 1})["type"],
        as_block("check_inbox", {"messages": [{}]})["type"],
        as_block("search_web_jobs", [{"title": "x"}])["type"],
        as_block("analyze_job_match", {"job": {}, "match": {}})["type"],
        as_block("improve_resume", {"suggestions": [{}]})["type"],
        as_block("generate_cover_letter", {"body": "x"})["type"],
    }
    assert produced <= rendered


# ── context hint ─────────────────────────────────────────────────────────


def test_the_side_panel_follows_what_the_agent_touched():
    assert as_context_hint("evaluate_candidate", {"candidate_id": "c1"}) == {
        "type": "candidate",
        "id": "c1",
    }
    assert as_context_hint("rank_candidates", {"job_id": "j1"}) == {"type": "job", "id": "j1"}


def test_no_hint_without_a_record():
    assert as_context_hint("list_jobs", {}) is None
    assert as_context_hint("get_candidate", {}) is None
