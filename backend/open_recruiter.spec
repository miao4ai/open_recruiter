# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Open Recruiter backend.

Build:  cd backend && pyinstaller open_recruiter.spec
Output: backend/dist/backend/  (directory with backend.exe + dependencies)

Before building, run the build script to:
  1. Build frontend:  cd frontend && npm run build
  2. Pre-download embedding model into backend/models/
"""

from pathlib import Path

block_cipher = None

backend_dir = Path(SPECPATH)
project_root = backend_dir.parent
frontend_dist = project_root / "frontend" / "dist"
bundled_models = backend_dir / "models"

# ── Data files to bundle ──────────────────────────────────────────────────

datas = []

# Frontend static build (served by FastAPI)
if frontend_dist.is_dir():
    datas.append((str(frontend_dist), "frontend/dist"))
else:
    print("WARNING: frontend/dist not found — run 'npm run build' in frontend/ first")

# Pre-downloaded sentence-transformers model
if bundled_models.is_dir():
    datas.append((str(bundled_models), "models"))
else:
    print("WARNING: backend/models/ not found — embedding model won't be bundled")

# ── Hidden imports ────────────────────────────────────────────────────────

hiddenimports = [
    # Uvicorn internals
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # App modules
    "app",
    "app.main",
    "app.database",
    "app.vectorstore",
    "app.config",
    "app.auth",
    "app.llm",
    "app.models",
    "app.prompts",
    "app.scheduler",
    "app.automation_tasks",
    "app.routes",
    "app.routes.agent",
    "app.routes.auth",
    "app.routes.automations",
    "app.routes.calendar",
    "app.routes.candidates",
    "app.routes.emails",
    "app.routes.jobs",
    "app.routes.profile",
    "app.routes.search",
    "app.routes.seeker",
    "app.routes.settings",
    "app.agents",
    "app.agents.communication",
    "app.agents.employer",
    "app.agents.jd",
    "app.agents.job_search",
    "app.agents.market",
    "app.agents.matching",
    "app.agents.orchestrator",
    "app.agents.planning",
    "app.agents.resume",
    "app.agents.scheduling",
    "app.tools",
    "app.tools.email_sender",
    "app.tools.imap_checker",
    "app.tools.resume_parser",
    "app.slack",
    "app.slack.bot",
    "app.slack.handlers",
    "app.slack.normalizer",
    "app.slack.notifier",
    "app.slack.pipeline",
    "app.slack.privacy",
    "app.slack.routes",
    # ChromaDB & vector search
    "chromadb",
    "chromadb.api",
    "chromadb.config",
    "hnswlib",
    # Sentence transformers / ML
    "sentence_transformers",
    "torch",
    # Database
    "aiosqlite",
    "sqlite3",
    # Web / HTTP
    "sse_starlette",
    "httpx",
    "aiohttp",
    "multipart",
    # LLM
    "litellm",
    # Doc parsing
    "pymupdf",
    "fitz",
    "docx",
    # Auth / crypto
    "bcrypt",
    "jwt",
    # Scheduling
    "apscheduler",
    "apscheduler.schedulers.background",
    "apscheduler.triggers.interval",
    # Search
    "ddgs",
    # Misc
    "dotenv",
    "email",
    "email.mime",
    "email.mime.text",
    "email.mime.multipart",
]

# ── Analysis ──────────────────────────────────────────────────────────────

a = Analysis(
    ["run_server.py"],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PIL",
        "notebook",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Console window for logging; Electron hides it
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="backend",
)
