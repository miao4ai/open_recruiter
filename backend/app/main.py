"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import require_recruiter
from app.database import init_db
from app.routes import agent, auth, automations, calendar, candidates, emails, jobs, profile, search, seeker, settings
from app.scheduler import init_scheduler, shutdown_scheduler
from app.slack import routes as slack_routes
from app.slack.bot import init_slack_app
from app.vectorstore import init_vectorstore


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_vectorstore()

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
