"""Tools for the other side of the table: someone looking for a job.

The recruiting tools in `recruiting.py` answer "who should I hire". These answer
"where should I apply", and they are a separate set rather than more entries in
the same registry because the two audiences must not see each other's tools — a
job seeker's assistant has no business calling `set_candidate_status`.

Three properties shape them, all of them for chat clients:

*Stateless where it can be.* A résumé arrives as text and is embedded for the
length of one call; nothing is stored and nothing is indexed, so one deployment
serves many people. `apply_to_job` is the exception, and it says so.

*No model in the common path.* `search_jobs` and `recommend_jobs` run on
keywords and vectors. A seeker browsing roles should not cost a completion per
tap, and these keep working when no model key is configured at all.

*Cards, as one JSON string.* Connectors render a search result from
`{id, title, subtitle, price, detail, url, fields}` with string values in
`fields`, and read it from the first text block — so a Python list would be
split into one block per item and a reader taking the first would silently see
one result. The shape is the one `product/backend/app/mcp_server.py` already
serves, deliberately: a caller pointed at either gets the same answer.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from openrecruiter.tools.base import Tool
from openrecruiter.types import Candidate, Job, Match

if TYPE_CHECKING:  # pragma: no cover
    from openrecruiter.client import Recruiter

log = logging.getLogger(__name__)

# How much of a résumé is embedded. Past this the vector stops sharpening and
# the request just costs more.
RESUME_EMBED_CHARS = 4000

# Postings name roles in English; a seeker tapping a Chinese or Japanese button
# does not. Longest phrases first, so 机器学习工程师 is not split into
# 机器学习 + 工程师 before the whole phrase is tried.
ROLE_ALIASES = {
    "机器学习工程师": "machine learning engineer", "機械学習エンジニア": "machine learning engineer",
    "机器学习": "machine learning", "機械学習": "machine learning", "算法工程师": "machine learning engineer",
    "数据科学家": "data scientist", "データサイエンティスト": "data scientist", "数据分析": "data analyst",
    "后端工程师": "backend engineer", "后端": "backend", "バックエンド": "backend", "服务端": "backend",
    "前端工程师": "frontend engineer", "前端": "frontend", "フロントエンド": "frontend",
    "ios工程师": "ios engineer", "ios 工程师": "ios engineer", "iosエンジニア": "ios engineer",
    "安卓": "android", "アンドロイド": "android",
    "产品经理": "product manager", "プロダクトマネージャー": "product manager", "プロダクトマネジャー": "product manager",
    "研究员": "research", "研究エンジニア": "research engineer", "运维": "sre", "语音": "speech", "音声": "speech",
    "计算机视觉": "computer vision", "自然语言处理": "nlp", "自然言語処理": "nlp",
    "工程师": "engineer", "エンジニア": "engineer", "开发": "developer", "実装": "developer",
    # Not only tech.
    "会计": "accountant", "経理": "accountant", "财务分析": "financial analyst", "财务": "finance", "財務": "finance",
    "设计师": "designer", "デザイナー": "designer", "设计": "design", "デザイン": "design",
    "销售": "sales", "営業": "sales", "市场": "marketing", "マーケ": "marketing", "マーケティング": "marketing",
    "客服": "customer support", "カスタマーサポート": "customer support", "运营": "operations", "運営": "operations",
    "人事": "hr", "人事担当": "hr", "招聘": "recruiting", "教师": "teacher", "老师": "teacher", "教師": "teacher", "英语": "english",
    "护士": "nurse", "看護師": "nurse", "律师": "legal", "法务": "legal", "翻译": "translator", "翻訳": "translator",
    "游戏策划": "game designer", "ゲームデザイナー": "game designer", "数据工程师": "data engineer",
}
_ROLE_KEYS = sorted(ROLE_ALIASES, key=len, reverse=True)

# Postings spell places in English; a seeker chatting in Chinese or Japanese
# does not. The common ones, so 东京 finds Tokyo without a model in the way.
LOCATION_ALIASES = {
    "东京": "tokyo", "東京": "tokyo", "大阪": "osaka", "京都": "kyoto", "名古屋": "nagoya",
    "福冈": "fukuoka", "福岡": "fukuoka", "横滨": "yokohama", "横浜": "yokohama",
    "札幌": "sapporo", "神户": "kobe", "神戸": "kobe", "日本": "japan",
    "北京": "beijing", "上海": "shanghai", "深圳": "shenzhen", "香港": "hong kong",
    "台北": "taipei", "新加坡": "singapore", "シンガポール": "singapore",
    "远程": "remote", "遠程": "remote", "リモート": "remote", "在宅": "remote",
    "任意": "", "无所谓": "", "哪里都行": "", "どこでも": "",
    "成都": "chengdu", "杭州": "hangzhou", "广州": "guangzhou", "南京": "nanjing", "武汉": "wuhan",
    "首尔": "seoul", "ソウル": "seoul", "曼谷": "bangkok", "悉尼": "sydney", "シドニー": "sydney",
    "伦敦": "london", "ロンドン": "london", "纽约": "new york", "ニューヨーク": "new york",
    "旧金山": "san francisco", "湾区": "bay area",
    "西雅图": "seattle", "柏林": "berlin", "ベルリン": "berlin", "巴黎": "paris", "パリ": "paris",
    "美国": "us", "アメリカ": "us", "欧洲": "eu", "全球": "global", "海外": "",
}

_STR = {"type": "string"}
_INT = {"type": "integer"}


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


# ── the pieces the tools share ───────────────────────────────────────────────


def transient_candidate(resume_text: str) -> Candidate:
    """A `Candidate` for the length of one call, never stored.

    The text rides in `resume_summary` because `Candidate.embed_text()` reads
    summary, skills and title and ignores `raw_resume_text` — put it only in the
    raw field and the embedding comes out empty.
    """
    return Candidate(
        resume_summary=(resume_text or "")[:RESUME_EMBED_CHARS],
        raw_resume_text=resume_text or "",
    )


def english_roles(query: str) -> str:
    """Rewrite role words a posting would spell in English."""
    q = (query or "").lower()
    for key in _ROLE_KEYS:
        if key in q:
            q = q.replace(key, " " + ROLE_ALIASES[key] + " ")
    return q


def normalise_location(location: str) -> str:
    raw = (location or "").strip()
    return LOCATION_ALIASES.get(raw, raw.lower())


def job_card(job: Job, score: float | None = None) -> dict[str, Any]:
    """One search-result card. Every value in `fields` is a string by contract."""
    where = " · ".join(p for p in (job.company, job.location) if p)
    if job.remote:
        where = f"{where} · Remote" if where else "Remote"
    fields = {
        "company": job.company or "",
        "location": job.location or "",
        "remote": "true" if job.remote else "false",
        "posted_date": job.created_at or "",
    }
    if job.required_skills:
        fields["skills"] = ", ".join(job.required_skills[:8])
    if score is not None:
        fields["score"] = f"{score:.2f}"
    return {
        "id": job.id,
        "title": job.title or "",
        "subtitle": where,
        "price": job.salary_range or "",
        "detail": (job.summary or job.raw_text or "").strip()[:280],
        "url": "",
        "fields": fields,
    }


def _matches_location(job: Job, loc: str) -> bool:
    if not loc:
        return True
    if loc in (job.location or "").lower():
        return True
    return loc == "remote" and job.remote


def build_seeker_tools(client: "Recruiter") -> list[Tool]:
    """The job-seeker tool set, bound to a client."""

    def search_jobs(query: str = "", location: str = "", top_k: int = 10) -> str:
        top = max(1, int(top_k))
        tokens = [t for t in re.split(r"[\s,、/]+", english_roles(query).lower()) if t]

        # Meaning first, words second: with embeddings configured the query goes
        # through the vector index — any language, any phrasing — and the
        # location filter applies to what comes back.
        if tokens and client.index.available:
            loc = normalise_location(location)
            cards = []
            for job_id, score in client.index.search_jobs(
                transient_candidate(query), top_k=top * 3
            ):
                job = client.store.get_job(job_id)
                if job is None or not _matches_location(job, loc):
                    continue
                cards.append(job_card(job, score=score))
                if len(cards) >= top:
                    break
            return json.dumps(cards, ensure_ascii=False)

        loc = normalise_location(location)
        scored = []
        for job in client.store.list_jobs(limit=1000):
            if not _matches_location(job, loc):
                continue
            hay = " ".join(
                [job.title or "", job.company or "", job.summary or "", job.raw_text or ""]
                + job.required_skills
            ).lower()
            hits = sum(1 for t in tokens if t in hay)
            if tokens and hits == 0:
                continue
            scored.append((hits, job))
        # Stable sort keeps the store's own order (newest first) within a tie.
        scored.sort(key=lambda p: p[0], reverse=True)
        return json.dumps([job_card(j) for _, j in scored[:top]], ensure_ascii=False)

    def recommend_jobs(resume_text: str, top_k: int = 5) -> str:
        text = (resume_text or "").strip()
        if not text or not client.index.available:
            return "[]"
        cards = []
        for job_id, score in client.index.search_jobs(
            transient_candidate(text), top_k=max(1, int(top_k))
        ):
            job = client.store.get_job(job_id)
            if job is not None:
                cards.append(job_card(job, score=score))
        return json.dumps(cards, ensure_ascii=False)

    def match_resume_to_job(resume_text: str, job_id: str) -> dict:
        from openrecruiter.ranking.api import APIRanker

        job = client.store.get_job(job_id)
        if job is None:
            return {"job_id": job_id, "score": 0.0, "reasoning": "Job not found."}
        return APIRanker(client.llm).score(job, transient_candidate(resume_text)).model_dump()

    def apply_to_job(
        job_id: str,
        resume_text: str,
        name: str = "",
        email: str = "",
        source: str = "",
        note: str = "",
    ) -> str:
        job = client.store.get_job((job_id or "").strip()) if job_id else None
        if job is None:
            return json.dumps({"ok": False, "message": f"no open job with id {job_id!r}"})
        text = (resume_text or "").strip()
        if not text:
            return json.dumps({"ok": False, "message": "no resume text"})

        # Stored directly rather than through `add_candidate`, which parses the
        # résumé with a model first: an application must not fail because no
        # model key is configured.
        candidate = transient_candidate(text)
        candidate.name = name.strip() or candidate.name
        candidate.email = email.strip() or candidate.email
        client.store.add_candidate(candidate)

        # A `Match` with no score is how this store records "these two are
        # related" — it is what `list_matches(job_id)` reads on the other side.
        reason = " · ".join(
            p
            for p in (
                f"applied via {source.strip()}" if source.strip() else "applied",
                note.strip(),
            )
            if p
        )
        client.store.save_match(
            Match(candidate_id=candidate.id, job_id=job.id, reasoning=reason, ranker="application")
        )
        try:
            client.index.index_candidate(candidate)
        except Exception as exc:  # noqa: BLE001 - ranking is a bonus; the application stands
            log.warning("Could not index applicant %s: %s", candidate.id, exc)
        return json.dumps(
            {
                "ok": True,
                "candidate_id": candidate.id,
                "job_id": job.id,
                "title": job.title,
                "company": job.company,
                "message": "in the pipeline as a new candidate",
            },
            ensure_ascii=False,
        )

    return [
        Tool(
            name="search_jobs",
            description=(
                "Search open jobs by keywords (title, company, skills, description) and/or "
                'location ("remote" matches remote jobs). No LLM. Returns a JSON array of job '
                "cards: id, title, subtitle (company · location), price (salary), detail, "
                "fields{company, location, remote, posted_date, skills}."
            ),
            parameters=_obj({"query": _STR, "location": _STR, "top_k": _INT}),
            fn=search_jobs,
        ),
        Tool(
            name="recommend_jobs",
            description=(
                "Recommend open jobs for a resume (vector similarity, no LLM, nothing stored). "
                "Returns a JSON array of job cards best-first, each with fields.score (0–1). "
                "Empty when embeddings are not configured."
            ),
            parameters=_obj({"resume_text": _STR, "top_k": _INT}, ["resume_text"]),
            fn=recommend_jobs,
        ),
        Tool(
            name="match_resume_to_job",
            description=(
                "LLM judgement of one resume (text) against one job. Returns score (0–1), "
                "strengths, gaps, reasoning. Nothing is stored."
            ),
            parameters=_obj({"resume_text": _STR, "job_id": _STR}, ["resume_text", "job_id"]),
            fn=match_resume_to_job,
        ),
        Tool(
            name="apply_to_job",
            description=(
                "Submit a resume to one open job: the seeker becomes a candidate in that job's "
                'pipeline (status "new"), visible to the recruiter side at once. This is the one '
                "tool here that changes the recruiter's world — ask the person first. Returns a "
                "JSON object {ok, candidate_id, job_id, title, company, message}."
            ),
            parameters=_obj(
                {
                    "job_id": _STR,
                    "resume_text": _STR,
                    "name": _STR,
                    "email": _STR,
                    "source": _STR,
                    "note": _STR,
                },
                ["job_id", "resume_text"],
            ),
            fn=apply_to_job,
            requires_approval=True,
        ),
    ]


#: The one tool here that writes. Hosts gate on this rather than on a name list
#: of their own.
SEEKER_WRITE_TOOLS = frozenset({"apply_to_job"})


__all__ = [
    "LOCATION_ALIASES",
    "ROLE_ALIASES",
    "SEEKER_WRITE_TOOLS",
    "build_seeker_tools",
    "english_roles",
    "job_card",
    "normalise_location",
    "transient_candidate",
]
