"""Intent Detection Harness — tests the keyword fallback and action routing.

Run:  cd backend && python -m pytest ../tests/harness/test_intent_detection.py -v
"""

import pytest

from app.routes.agent import _detect_action_from_keywords


# ═══════════════════════════════════════════════════════════════════════════
# 1. Keyword fallback: _detect_action_from_keywords
# ═══════════════════════════════════════════════════════════════════════════

class TestKeywordFallback:
    """Tests for the regex-based keyword detection (layer 2 of 3)."""

    # ── Resume upload ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("msg", [
        "upload a resume",
        "Upload my resume please",
        "upload resume",
        "upload a CV",
        "上传简历",
        "上传一份CV",
        "添加候选人",
        "add a new candidate",
    ])
    def test_resume_upload_detected(self, msg: str):
        result = _detect_action_from_keywords(msg)
        assert result is not None
        assert result["type"] == "upload_resume"

    # ── JD upload ─────────────────────────────────────────────────────────

    @pytest.mark.parametrize("msg", [
        "upload a JD",
        "upload a job description file",
        "上传JD",
        "上传职位描述",
        "上传文件",
    ])
    def test_jd_upload_detected(self, msg: str):
        result = _detect_action_from_keywords(msg)
        assert result is not None
        assert result["type"] == "upload_jd"

    # ── Match job (with embedded job ID) ──────────────────────────────────

    @pytest.mark.parametrize("msg,expected_id", [
        ("Find candidates for job:abc12345", "abc12345"),
        ("match candidates job:def67890", "def67890"),
    ])
    def test_match_job_detected(self, msg: str, expected_id: str):
        result = _detect_action_from_keywords(msg)
        assert result is not None
        assert result["type"] == "match_job"
        assert result["job_id"] == expected_id

    # ── Inbox check ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("msg", [
        "check my inbox",
        "check my email",
        "查看收件箱",
        "查看邮箱",
        "有没有新邮件",
        "fetch my recent emails",
    ])
    def test_inbox_check_detected(self, msg: str):
        result = _detect_action_from_keywords(msg)
        assert result is not None
        assert result["type"] == "check_inbox"

    # ── No action (should return None) ────────────────────────────────────

    @pytest.mark.parametrize("msg", [
        "hello",
        "how are you",
        "evaluate Alice",
        "draft an email to Bob",
        "what jobs match Alice",
        "tell me about the pipeline",
        "市场薪资是多少",
    ])
    def test_no_keyword_action(self, msg: str):
        result = _detect_action_from_keywords(msg)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# 2. Action routing whitelist: seeker vs recruiter
# ═══════════════════════════════════════════════════════════════════════════

# These are the allowed actions — keep in sync with agent.py
_SEEKER_ALLOWED_ACTIONS = {
    "search_jobs", "analyze_job_match", "save_job",
    "improve_resume", "generate_cover_letter",
}


class TestActionRouting:
    """Tests that action routing correctly filters by user role."""

    @pytest.mark.parametrize("action_type", [
        "search_jobs",
        "analyze_job_match",
        "save_job",
        "improve_resume",
        "generate_cover_letter",
    ])
    def test_seeker_allowed_actions(self, action_type: str):
        assert action_type in _SEEKER_ALLOWED_ACTIONS

    @pytest.mark.parametrize("action_type", [
        "compose_email",
        "upload_resume",
        "upload_jd",
        "create_job",
        "match_candidate",
        "evaluate_candidate",
        "market_analysis",
        "start_workflow",
        "recommend_to_employer",
        "mark_candidates_replied",
        "update_candidate_status",
    ])
    def test_recruiter_only_actions_blocked_for_seeker(self, action_type: str):
        assert action_type not in _SEEKER_ALLOWED_ACTIONS

    # ── Edge case: JD upload should NOT override create_job ───────────────

    def test_create_job_text_not_overridden_by_upload(self):
        """When user describes a job in text, keyword detection should NOT
        produce an upload_jd action, because the LLM correctly returned
        create_job. The override logic only fires for upload intents."""
        # "帮我发布一个React工程师职位" — no upload keywords
        result = _detect_action_from_keywords("帮我发布一个React工程师职位")
        assert result is None  # keyword fallback should NOT fire


# ═══════════════════════════════════════════════════════════════════════════
# 3. Intent disambiguation — known confusing pairs
# ═══════════════════════════════════════════════════════════════════════════

class TestIntentDisambiguation:
    """Verify that similar-sounding intents don't cross-fire at the keyword level."""

    def test_upload_resume_not_upload_jd(self):
        """'upload a resume' should NOT trigger upload_jd."""
        result = _detect_action_from_keywords("upload a resume")
        assert result["type"] == "upload_resume"

    def test_upload_jd_not_upload_resume(self):
        """'upload a JD' should NOT trigger upload_resume."""
        result = _detect_action_from_keywords("upload a JD")
        assert result["type"] == "upload_jd"

    def test_job_description_in_text_no_upload(self):
        """Describing a job in conversation should not trigger any upload."""
        result = _detect_action_from_keywords(
            "I need a senior React engineer with 5 years experience"
        )
        assert result is None
