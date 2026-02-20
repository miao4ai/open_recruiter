"""FastAPI application entry point."""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth import require_recruiter
from app.database import init_db
from app.routes import agent, auth, automations, calendar, candidates, emails, jobs, profile, search, seeker, settings
from app.scheduler import init_scheduler, shutdown_scheduler
from app.slack import routes as slack_routes
from app.slack.bot import init_slack_app
from app.vectorstore import init_vectorstore

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    try:
        init_vectorstore()
    except Exception:
        log.exception("Failed to initialise vector store — semantic search will be unavailable")

    # Initialize Slack bot (gracefully skips if tokens not configured)
    from app.routes.settings import get_config
    cfg = get_config()
    init_slack_app(cfg)

    # Start background automation scheduler
    init_scheduler()

    yield

    # Graceful shutdown
    shutdown_scheduler()


app = FastAPI(title="Open Recruiter API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_recruiter_only = [Depends(require_recruiter)]

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"], dependencies=_recruiter_only)
app.include_router(candidates.router, prefix="/api/candidates", tags=["candidates"], dependencies=_recruiter_only)
app.include_router(emails.router, prefix="/api/emails", tags=["emails"], dependencies=_recruiter_only)
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"], dependencies=_recruiter_only)
app.include_router(search.router, prefix="/api/search", tags=["search"], dependencies=_recruiter_only)
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"], dependencies=_recruiter_only)
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(seeker.router, prefix="/api/seeker", tags=["seeker"])
app.include_router(automations.router, prefix="/api/automations", tags=["automations"], dependencies=_recruiter_only)
app.include_router(slack_routes.router, prefix="/slack", tags=["slack"])


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Serve React static build (production / Electron mode) ────────────────
# Only mounted when frontend/dist exists (i.e. after `npm run build`).

# PyInstaller bundles data files under sys._MEIPASS; normal dev uses relative path
_meipass = getattr(sys, "_MEIPASS", None)
_FRONTEND_DIST = None

# Search multiple candidate paths for frontend dist
for _candidate in [
    Path(_meipass) / "frontend" / "dist" if _meipass else None,
    Path(sys.executable).parent / "_internal" / "frontend" / "dist",
    Path(sys.executable).parent / "frontend" / "dist",
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
]:
    if _candidate and _candidate.is_dir() and (_candidate / "index.html").is_file():
        _FRONTEND_DIST = _candidate
        break

if _FRONTEND_DIST:
    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="static-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str):
        """Serve static files or fall back to index.html for SPA routing."""
        file_path = _FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_FRONTEND_DIST / "index.html")
