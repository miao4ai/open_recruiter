"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import agent, auth, calendar, candidates, emails, jobs, search, settings
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

    yield


app = FastAPI(title="Open Recruiter API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(candidates.router, prefix="/api/candidates", tags=["candidates"])
app.include_router(emails.router, prefix="/api/emails", tags=["emails"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(slack_routes.router, prefix="/slack", tags=["slack"])


@app.get("/health")
async def health():
    return {"status": "ok"}
