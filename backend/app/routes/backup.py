"""Data backup & restore — export/import ZIP containing SQLite DB + uploads."""

from __future__ import annotations

import io
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.database import DB_PATH

router = APIRouter()

# uploads directory (same as candidates.py / emails.py)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_UPLOADS_DIR = _BACKEND_ROOT / "uploads"


@router.get("/export")
async def export_backup(_user: dict = Depends(get_current_user)):
    """Export a ZIP containing the SQLite database and all uploaded files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. SQLite DB — use backup API for a safe, consistent copy
        if DB_PATH.exists():
            db_bytes = io.BytesIO()
            src = sqlite3.connect(str(DB_PATH))
            dst = sqlite3.connect(":memory:")
            src.backup(dst)
            src.close()
            # Dump memory db to bytes
            for line in dst.iterdump():
                db_bytes.write((line + "\n").encode("utf-8"))
            dst.close()
            zf.writestr("open_recruiter.sql", db_bytes.getvalue())

            # Also include raw .db for fast restore
            zf.write(str(DB_PATH), "open_recruiter.db")

        # 2. Uploaded files (resumes, JDs, etc.)
        if _UPLOADS_DIR.exists():
            for fpath in _UPLOADS_DIR.rglob("*"):
                if fpath.is_file():
                    arcname = f"uploads/{fpath.relative_to(_UPLOADS_DIR)}"
                    zf.write(str(fpath), arcname)

    buf.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"open_recruiter_backup_{timestamp}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_backup(
    file: UploadFile = File(...),
    _user: dict = Depends(get_current_user),
):
    """Import a backup ZIP. Replaces the current database and uploads."""
    content = await file.read()
    buf = io.BytesIO(content)

    try:
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()

            # Validate — must contain either the .db or .sql file
            has_db = "open_recruiter.db" in names
            has_sql = "open_recruiter.sql" in names
            if not has_db and not has_sql:
                return {"status": "error", "message": "Invalid backup: no database found in ZIP"}

            # 1. Restore database
            if has_db:
                db_data = zf.read("open_recruiter.db")
                # Validate it's a real SQLite file
                if not db_data[:16].startswith(b"SQLite format 3"):
                    return {"status": "error", "message": "Invalid backup: corrupt database file"}

                # Create backup of current DB before overwriting
                if DB_PATH.exists():
                    backup_path = DB_PATH.with_suffix(
                        f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    )
                    shutil.copy2(str(DB_PATH), str(backup_path))

                DB_PATH.write_bytes(db_data)

            # 2. Restore uploads
            upload_entries = [n for n in names if n.startswith("uploads/") and not n.endswith("/")]
            if upload_entries:
                for entry in upload_entries:
                    rel = entry[len("uploads/"):]  # strip "uploads/" prefix
                    dest = _UPLOADS_DIR / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(entry))

    except zipfile.BadZipFile:
        return {"status": "error", "message": "Invalid file: not a valid ZIP archive"}

    return {"status": "ok", "message": "Backup restored. Please restart the application."}
