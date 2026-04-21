"""Voice transcription — local Whisper via faster-whisper.

POST /api/transcribe  (multipart: file=<audio blob>)
Returns: {"text": "..."}
"""

from __future__ import annotations

import logging
import os
import tempfile
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.auth import get_current_user

log = logging.getLogger(__name__)

router = APIRouter()

# Keep the model tiny on low-power hardware (e.g. Raspberry Pi).
# Override via WHISPER_MODEL env: tiny | base | small | medium | large-v3
_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE", "int8")

_model = None
_model_lock = Lock()
_model_err: str | None = None


def _get_model():
    """Lazy-load the Whisper model on first request."""
    global _model, _model_err
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from faster_whisper import WhisperModel
            log.info("Loading Whisper model '%s' (compute=%s)…", _MODEL_NAME, _COMPUTE_TYPE)
            _model = WhisperModel(_MODEL_NAME, device="cpu", compute_type=_COMPUTE_TYPE)
            log.info("Whisper model loaded.")
        except Exception as e:
            _model_err = str(e)
            log.exception("Failed to load Whisper model")
            raise
    return _model


@router.post("")
async def transcribe(
    file: UploadFile = File(...),
    _user: dict = Depends(get_current_user),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    # faster-whisper reads from a filesystem path; write to a temp file.
    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        model = _get_model()
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(status_code=503, detail=f"Whisper unavailable: {e}")

    try:
        segments, info = model.transcribe(tmp_path, vad_filter=True, beam_size=1)
        text = " ".join(s.text.strip() for s in segments).strip()
        return {"text": text, "language": info.language}
    except Exception as e:
        log.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
