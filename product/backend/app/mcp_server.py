"""MCP server — exposes Open Recruiter's matching & evaluation capabilities.

Runs as a standalone stdio process so any MCP client (Claude Desktop, Cursor,
another chat agent, …) can call the recruiter's matching and evaluation tools.
It imports the existing agent/db functions directly and operates on the same
local SQLite + ChromaDB data — the FastAPI backend does NOT need to be running.

Run it with::

    uv run recruiter-mcp                              # stdio (Claude Desktop, Cursor)
    RECRUITER_MCP_TRANSPORT=http uv run recruiter-mcp # streamable HTTP for a server-side
                                                      # caller (charbit) — see _http_options

See ``skills/mcp.md`` for client wiring.
"""

import json
import logging
import os
import re
import sys

# The MCP Python SDK renamed FastMCP to MCPServer in 2.0. The three APIs we use
# — construction, @tool(), and run() over stdio — are identical across both, so
# support whichever is installed rather than pinning to an old major.
try:
    from mcp.server.mcpserver import MCPServer as _Server  # mcp >= 2.0
except ImportError:  # pragma: no cover - depends on the installed SDK
    from mcp.server.fastmcp import FastMCP as _Server  # mcp 1.x

from openrecruiter.types import Candidate

from app import database as db

log = logging.getLogger(__name__)

mcp = _Server("open-recruiter")


def _cfg():
    """Active runtime config (LLM provider, keys). Imported lazily so the
    module loads even before init_db()."""
    from app.routes.settings import get_config
    return get_config()


# ── Lookup helpers (read-only) ──────────────────────────────────────────────
# Matching/evaluation tools need job_id / candidate_id; these let a caller
# resolve names → IDs first.


@mcp.tool()
def list_jobs() -> list[dict]:
    """List all open jobs. Returns id, title, company, location for each —
    use the id as ``job_id`` in the matching/evaluation tools."""
    return [
        {
            "id": j["id"],
            "title": j.get("title", ""),
            "company": j.get("company", ""),
            "location": j.get("location", ""),
        }
        for j in (db.list_jobs() or [])
    ]


@mcp.tool()
def list_candidates(job_id: str = "", status: str = "") -> list[dict]:
    """List candidates, optionally filtered by ``job_id`` or pipeline
    ``status``. Returns id, name, current_title, current_company — use the id
    as ``candidate_id`` in the matching/evaluation tools."""
    rows = db.list_candidates(job_id=job_id or None, status=status or None) or []
    return [
        {
            "id": c["id"],
            "name": c.get("name", ""),
            "current_title": c.get("current_title", ""),
            "current_company": c.get("current_company", ""),
            "status": c.get("status", ""),
        }
        for c in rows
    ]


# ── Matching & evaluation ───────────────────────────────────────────────────


@mcp.tool()
def rank_candidates_for_job(job_id: str, top_k: int = 10) -> list[dict]:
    """Rank candidates for a job by semantic similarity (vector search, no LLM —
    fast). Returns candidates sorted best-first with a 0–1 ``score``."""
    from app.sdk_bridge import build_recruiter

    recruiter = build_recruiter(_cfg())
    job = recruiter.store.get_job(job_id)
    if job is None:
        return []

    out = []
    for cid, score in recruiter.index.search_candidates(job, top_k=top_k):
        cand = recruiter.store.get_candidate(cid)
        if cand is None:
            continue
        out.append({
            "candidate_id": cid,
            "name": cand.name or "Unknown",
            "current_title": cand.current_title,
            "current_company": cand.current_company,
            "experience_years": cand.experience_years,
            "skills": cand.skills[:8],
            "score": round(score, 4),
        })
    return out


@mcp.tool()
def match_candidate_to_job(job_id: str, candidate_id: str) -> dict:
    """Detailed LLM matching of one candidate against one job. Returns
    ``score`` (0–1), ``strengths``, ``gaps``, ``reasoning``."""
    from app.sdk_bridge import build_recruiter

    return build_recruiter(_cfg()).match(candidate_id, job_id).model_dump()


@mcp.tool()
def match_candidate_to_jobs(candidate_id: str) -> dict:
    """Match one candidate against ALL open jobs via LLM. Returns ``rankings``
    (each with job_id, title, company, score, strengths, gaps, one_liner) and a
    ``summary``."""
    from app.agents.planning import match_candidate_to_jobs as _match

    result = _match(_cfg(), candidate_id)
    # Drop the bulky raw candidate dict from the response.
    result.pop("candidate", None)
    return result


@mcp.tool()
def evaluate_candidate(candidate_id: str, job_id: str = "") -> dict:
    """Multi-agent (resume / culture / risk / market) swarm evaluation of a
    candidate, optionally against a specific job. Returns per-dimension scores,
    an ``overall_score`` (0–100), a ``hire_recommendation`` and a ``synthesis``."""
    from app.agents.evaluation_swarm import evaluate_candidate_swarm

    return evaluate_candidate_swarm(_cfg(), candidate_id, job_id=job_id)


# ── Job-seeker tools (stateless) ────────────────────────────────────────────
# Called by a chat app on a USER's behalf (charbit's recruiter skill): the
# resume arrives as text and nothing is stored or indexed, so one shared
# instance can serve many people without their data landing in this database.
#
# These return a JSON string, not a list: the MCP SDK splits a list result into
# one text block per item, and the caller (charbit's connector, like its
# mcp-suumo partner) reads the FIRST text block as one array of search cards
# {id, title, subtitle, price, detail, url, fields}. `fields` values are
# strings because that side decodes them as map[string]string.

_RESUME_EMBED_CHARS = 8000


def _transient_candidate(resume_text: str) -> Candidate:
    """A Candidate for this call only. The resume rides in ``resume_summary``
    because ``Candidate.embed_text()`` reads summary/skills/title and ignores
    ``raw_resume_text`` — put the text there and the embedding is empty."""
    return Candidate(
        resume_summary=resume_text[:_RESUME_EMBED_CHARS],
        raw_resume_text=resume_text,
    )


def _skills(row: dict) -> list[str]:
    s = row.get("required_skills") or []
    return json.loads(s) if isinstance(s, str) else list(s)


def _job_card(row: dict, score: float | None = None) -> dict:
    where = " · ".join(p for p in (row.get("company", ""), row.get("location", "")) if p)
    if row.get("remote"):
        where = f"{where} · Remote" if where else "Remote"
    fields = {
        "company": row.get("company") or "",
        "location": row.get("location") or "",
        "remote": "true" if row.get("remote") else "false",
        "posted_date": row.get("posted_date") or "",
    }
    if skills := _skills(row):
        fields["skills"] = ", ".join(skills[:8])
    if score is not None:
        fields["score"] = f"{score:.2f}"
    return {
        "id": row["id"],
        "title": row.get("title") or "",
        "subtitle": where,
        "price": row.get("salary_range") or "",
        "detail": (row.get("summary") or row.get("raw_text") or "").strip()[:280],
        "url": "",
        "fields": fields,
    }


@mcp.tool()
def apply_to_job(job_id: str, resume_text: str, name: str = "", email: str = "",
                 source: str = "", note: str = "") -> str:
    """Submit a resume to one open job: the seeker becomes a candidate in that
    job's pipeline (status "new"), visible to the recruiter side at once. This
    is the one tool here that changes the recruiter's world — callers ask the
    person first. Returns a JSON object {ok, candidate_id, job_id, title,
    company, message}."""
    row = db.get_job(job_id.strip()) if job_id else None
    if not row:
        return json.dumps({"ok": False, "message": f"no open job with id {job_id!r}"})
    text = (resume_text or "").strip()
    if not text:
        return json.dumps({"ok": False, "message": "no resume text"})
    cand = _transient_candidate(text)
    cand.name = name.strip() or cand.name
    cand.email = email.strip() or cand.email
    # Straight into the table: the SDK's add_candidate parses the resume with a
    # model first, and an application must not depend on a model key.
    db.insert_candidate({
        "id": cand.id, "name": cand.name, "email": cand.email, "phone": cand.phone,
        "current_title": cand.current_title, "current_company": cand.current_company,
        "skills": cand.skills, "experience_years": cand.experience_years, "location": cand.location,
        "resume_summary": cand.resume_summary, "status": "new",
        "created_at": cand.created_at, "updated_at": cand.created_at,
    })
    reason = " · ".join(p for p in (f"applied via {source.strip()}" if source.strip() else "applied", note.strip()) if p)
    db.insert_candidate_job({"candidate_id": cand.id, "job_id": row["id"], "pipeline_status": "new",
                             "match_reasoning": reason})
    try:
        from app.sdk_bridge import build_recruiter
        build_recruiter(_cfg()).index.index_candidate(cand)
    except Exception:  # noqa: BLE001 — ranking is a bonus; the application stands without it
        pass
    return json.dumps({"ok": True, "candidate_id": cand.id, "job_id": row["id"], "title": row.get("title", ""),
                       "company": row.get("company", ""), "message": "in the pipeline as a new candidate"},
                      ensure_ascii=False)


# Postings name roles in English; a seeker tapping a Chinese or Japanese role
# button does not. Longest phrases first so 机器学习工程师 is not split into
# 机器学习 + 工程师 before the whole phrase is tried.
_ROLE_ALIASES = {
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
_ROLE_KEYS = sorted(_ROLE_ALIASES, key=len, reverse=True)


def _english_roles(query: str) -> str:
    q = query.lower()
    for k in _ROLE_KEYS:
        if k in q:
            q = q.replace(k, " " + _ROLE_ALIASES[k] + " ")
    return q


# Postings spell places in English; a job seeker chatting in Chinese or Japanese
# does not. The common ones, so "东京" finds Tokyo without a model in the way.
_LOCATION_ALIASES = {
    "东京": "tokyo", "東京": "tokyo", "大阪": "osaka", "京都": "kyoto", "名古屋": "nagoya",
    "福冈": "fukuoka", "福岡": "fukuoka", "横滨": "yokohama", "横浜": "yokohama",
    "札幌": "sapporo", "神户": "kobe", "神戸": "kobe", "日本": "japan",
    "北京": "beijing", "上海": "shanghai", "深圳": "shenzhen", "香港": "hong kong",
    "台北": "taipei", "新加坡": "singapore", "シンガポール": "singapore",
    "远程": "remote", "遠程": "remote", "リモート": "remote", "在宅": "remote", "任意": "", "无所谓": "", "哪里都行": "", "どこでも": "",
    "成都": "chengdu", "杭州": "hangzhou", "广州": "guangzhou", "南京": "nanjing", "武汉": "wuhan",
    "首尔": "seoul", "ソウル": "seoul", "曼谷": "bangkok", "悉尼": "sydney", "シドニー": "sydney",
    "伦敦": "london", "ロンドン": "london", "纽约": "new york", "ニューヨーク": "new york", "旧金山": "san francisco", "湾区": "bay area",
    "西雅图": "seattle", "柏林": "berlin", "ベルリン": "berlin", "巴黎": "paris", "パリ": "paris", "美国": "us", "アメリカ": "us",
    "欧洲": "eu", "全球": "global", "海外": "",
}


@mcp.tool()
def search_jobs(query: str = "", location: str = "", top_k: int = 10) -> str:
    """Search open jobs by keywords (title, company, skills, description) and/or
    location ("remote" matches remote jobs). No LLM. Returns a JSON array of job
    cards: id, title, subtitle (company · location), price (salary), detail,
    fields{company, location, remote, posted_date, skills}."""
    tokens = [t for t in re.split(r"[\s,、/]+", _english_roles(query).lower()) if t]
    loc = _LOCATION_ALIASES.get(location.strip(), location.strip().lower())
    scored = []
    for row in db.list_jobs() or []:
        if loc and loc not in (row.get("location") or "").lower() \
                and not (loc == "remote" and row.get("remote")):
            continue
        hay = " ".join(
            str(row.get(k) or "") for k in ("title", "company", "summary", "raw_text")
        ).lower() + " " + " ".join(_skills(row)).lower()
        hits = sum(1 for t in tokens if t in hay)
        if tokens and hits == 0:
            continue
        scored.append((hits, row))
    # Stable sort: list_jobs is newest-first, so ties stay newest-first.
    scored.sort(key=lambda p: p[0], reverse=True)
    return json.dumps([_job_card(r) for _, r in scored[: max(1, int(top_k))]])


@mcp.tool()
def recommend_jobs(resume_text: str, top_k: int = 5) -> str:
    """Recommend open jobs for a resume (vector similarity, no LLM, nothing
    stored). Returns a JSON array of job cards best-first, each with
    fields.score (0–1). Empty when embeddings are not configured."""
    text = (resume_text or "").strip()
    if not text:
        return "[]"
    from app.sdk_bridge import build_recruiter

    recruiter = build_recruiter(_cfg())
    hits = recruiter.index.search_jobs(_transient_candidate(text), top_k=max(1, int(top_k)))
    cards = []
    for job_id, score in hits:
        row = db.get_job(job_id)
        if row is not None:
            cards.append(_job_card(row, score=score))
    return json.dumps(cards)


@mcp.tool()
def match_resume_to_job(resume_text: str, job_id: str) -> dict:
    """LLM judgement of one resume (text) against one job. Returns ``score``
    (0–1), ``strengths``, ``gaps``, ``reasoning``. Nothing is stored."""
    from openrecruiter.ranking.api import APIRanker

    from app.sdk_bridge import build_recruiter

    recruiter = build_recruiter(_cfg())
    job = recruiter.store.get_job(job_id)
    if job is None:
        return {"job_id": job_id, "score": 0.0, "reasoning": "Job not found."}
    return APIRanker(recruiter.llm).score(job, _transient_candidate(resume_text)).model_dump()


def _http_options() -> dict:
    """Streamable-HTTP options from the environment. Stateless + JSON responses
    is the mode a plain server-side caller fits: charbit's connector POSTs one
    JSON-RPC request at a time and reads a JSON body back — it never sends
    notifications/initialized and never opens an SSE stream."""
    return {
        "host": os.environ.get("RECRUITER_MCP_HOST", "127.0.0.1"),
        "port": int(os.environ.get("RECRUITER_MCP_PORT", "8765")),
        "streamable_http_path": "/mcp",
        "json_response": True,
        "stateless_http": True,
    }


class BearerGate:
    """Refuses any HTTP request without `Authorization: Bearer <token>` — the
    one header charbit's connector already sends (CHARBIT_RECRUITER_MCP_AUTH).
    Pure ASGI, wrapped around the MCP app, so the SDK never sees a stranger."""

    def __init__(self, app, token: str):
        self.app, self.expect = app, f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            auth = dict(scope.get("headers") or []).get(b"authorization", b"")
            if auth != self.expect:
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await self.app(scope, receive, send)


def http_app():
    """The streamable-HTTP ASGI app, gated by RECRUITER_MCP_TOKEN when set.
    Needs mcp>=2.0 (what the lock resolves)."""
    from mcp.server.transport_security import TransportSecuritySettings

    opts = _http_options()
    # DNS-rebinding protection is for servers on localhost; behind Cloud Run
    # (or any proxy) the Host header is the public one and would be refused.
    app = mcp.streamable_http_app(
        streamable_http_path=opts["streamable_http_path"], json_response=opts["json_response"],
        stateless_http=opts["stateless_http"],
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    if token := os.environ.get("RECRUITER_MCP_TOKEN", "").strip():
        app = BearerGate(app, token)
    return app


def main() -> None:
    """Entry point — init local stores, then serve over stdio (default) or
    streamable HTTP (RECRUITER_MCP_TRANSPORT=http)."""
    logging.basicConfig(level=logging.WARNING)
    from app.database import init_db
    init_db()
    # The vector index opens lazily on first search, so there is nothing to
    # initialise here — and nothing to fail before the server is listening.
    if os.environ.get("RECRUITER_MCP_TRANSPORT", "stdio").lower() == "http":
        import uvicorn

        opts = _http_options()
        gated = "token-gated" if os.environ.get("RECRUITER_MCP_TOKEN", "").strip() else "OPEN"
        print(f"recruiter-mcp: http://{opts['host']}:{opts['port']}{opts['streamable_http_path']} ({gated})",
              file=sys.stderr)
        uvicorn.run(http_app(), host=opts["host"], port=opts["port"], log_level="warning")
        return
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
