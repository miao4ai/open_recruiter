"""Voice transcription harness — tests /api/transcribe behavior.

The real Whisper model is mocked so tests run in milliseconds without
downloading model weights or shelling out to ctranslate2.

Run:  cd backend && python -m pytest ../tests/harness/test_transcribe.py -v
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.routes import transcribe as transcribe_module


# ── Fakes ─────────────────────────────────────────────────────────────────

class _FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeInfo:
    def __init__(self, language: str = "en") -> None:
        self.language = language


class _FakeModel:
    """Stand-in for faster_whisper.WhisperModel."""

    def __init__(
        self,
        segments: list[_FakeSegment] | None = None,
        info: _FakeInfo | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._segments = segments or [_FakeSegment("hello world")]
        self._info = info or _FakeInfo()
        self._raise = raise_exc
        self.last_path: str | None = None
        self.last_kwargs: dict[str, Any] | None = None

    def transcribe(self, path: str, **kwargs: Any):
        self.last_path = path
        self.last_kwargs = kwargs
        if self._raise:
            raise self._raise
        return iter(self._segments), self._info


# ── App fixtures ──────────────────────────────────────────────────────────

def _make_app(*, override_auth: bool = True) -> FastAPI:
    """Minimal FastAPI app with just the transcribe router mounted."""
    app = FastAPI()
    app.include_router(transcribe_module.router, prefix="/api/transcribe")
    if override_auth:
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "test-user",
            "email": "test@example.com",
        }
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_make_app())


@pytest.fixture
def client_real_auth() -> TestClient:
    return TestClient(_make_app(override_auth=False))


@pytest.fixture
def reset_model_cache():
    """Ensure the module-level model cache doesn't bleed between tests."""
    transcribe_module._model = None
    transcribe_module._model_err = None
    yield
    transcribe_module._model = None
    transcribe_module._model_err = None


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch, reset_model_cache) -> _FakeModel:
    """Default happy-path fake model installed via monkeypatch."""
    model = _FakeModel()
    monkeypatch.setattr(transcribe_module, "_get_model", lambda: model)
    return model


# ── Tests: auth ───────────────────────────────────────────────────────────

class TestAuth:
    """Endpoint must reject unauthenticated requests."""

    def test_missing_auth_header_rejected(self, client_real_auth: TestClient):
        resp = client_real_auth.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"audio-bytes", "audio/webm")},
        )
        # HTTPBearer rejects missing header with 403; an invalid token would be 401.
        assert resp.status_code in (401, 403)

    def test_invalid_token_rejected(self, client_real_auth: TestClient):
        resp = client_real_auth.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"audio-bytes", "audio/webm")},
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code == 401


# ── Tests: input validation ───────────────────────────────────────────────

class TestInputValidation:
    """Pre-model checks: file presence, empty body."""

    def test_missing_file_field_returns_422(self, client: TestClient):
        resp = client.post("/api/transcribe")
        assert resp.status_code == 422

    def test_empty_audio_returns_400(self, client: TestClient, fake_model: _FakeModel):
        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"", "audio/webm")},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()
        # Empty body short-circuits before the model is called.
        assert fake_model.last_path is None


# ── Tests: happy path ─────────────────────────────────────────────────────

class TestHappyPath:
    """Successful transcription cases."""

    def test_single_segment(self, client: TestClient, fake_model: _FakeModel):
        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"audio-bytes", "audio/webm")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "hello world"
        assert body["language"] == "en"

    def test_multiple_segments_joined_with_spaces(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        reset_model_cache,
    ):
        model = _FakeModel(
            segments=[
                _FakeSegment("Hello"),
                _FakeSegment(" there,"),
                _FakeSegment(" general Kenobi."),
            ],
        )
        monkeypatch.setattr(transcribe_module, "_get_model", lambda: model)

        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"x", "audio/webm")},
        )
        assert resp.status_code == 200
        # Each segment is .strip()'d then joined with a single space.
        assert resp.json()["text"] == "Hello there, general Kenobi."

    def test_outer_whitespace_trimmed(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        reset_model_cache,
    ):
        model = _FakeModel(segments=[_FakeSegment("   padded text   ")])
        monkeypatch.setattr(transcribe_module, "_get_model", lambda: model)

        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"x", "audio/webm")},
        )
        assert resp.json()["text"] == "padded text"

    def test_language_propagated_from_whisper(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        reset_model_cache,
    ):
        model = _FakeModel(
            segments=[_FakeSegment("你好")],
            info=_FakeInfo(language="zh"),
        )
        monkeypatch.setattr(transcribe_module, "_get_model", lambda: model)

        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"x", "audio/webm")},
        )
        assert resp.json()["language"] == "zh"

    def test_uses_vad_filter_and_beam_size_one(
        self, client: TestClient, fake_model: _FakeModel
    ):
        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"x", "audio/webm")},
        )
        assert resp.status_code == 200
        # Lock in the perf-tuned defaults for low-power hardware.
        assert fake_model.last_kwargs == {"vad_filter": True, "beam_size": 1}


# ── Tests: error paths ────────────────────────────────────────────────────

class TestErrors:
    """Model loading + transcription failure surfaces."""

    def test_model_load_failure_returns_503(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        reset_model_cache,
    ):
        def boom():
            raise RuntimeError("ctranslate2 missing")

        monkeypatch.setattr(transcribe_module, "_get_model", boom)

        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"x", "audio/webm")},
        )
        assert resp.status_code == 503
        assert "whisper unavailable" in resp.json()["detail"].lower()

    def test_transcription_failure_returns_500(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        reset_model_cache,
    ):
        model = _FakeModel(raise_exc=RuntimeError("decode error"))
        monkeypatch.setattr(transcribe_module, "_get_model", lambda: model)

        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"x", "audio/webm")},
        )
        assert resp.status_code == 500
        assert "transcription failed" in resp.json()["detail"].lower()


# ── Tests: temp-file lifecycle ────────────────────────────────────────────

class TestTempFileCleanup:
    """The route writes the upload to a tempfile and must clean it up
    on every code path (success, model-load failure, transcription failure)."""

    def test_temp_file_removed_on_success(
        self, client: TestClient, fake_model: _FakeModel
    ):
        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"audio-bytes", "audio/webm")},
        )
        assert resp.status_code == 200
        assert fake_model.last_path is not None
        assert not Path(fake_model.last_path).exists(), (
            f"Temp file {fake_model.last_path} should be removed after success"
        )

    def test_temp_file_removed_on_model_load_failure(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        reset_model_cache,
        tmp_path: Path,
    ):
        # Capture the temp path the route creates by spying on the tempfile module.
        captured: dict[str, str] = {}
        import tempfile as _tempfile
        real_named = _tempfile.NamedTemporaryFile

        def spy_named(*args, **kwargs):
            f = real_named(*args, **kwargs)
            captured["path"] = f.name
            return f

        monkeypatch.setattr(transcribe_module.tempfile, "NamedTemporaryFile", spy_named)
        monkeypatch.setattr(
            transcribe_module,
            "_get_model",
            lambda: (_ for _ in ()).throw(RuntimeError("no model")),
        )

        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"x", "audio/webm")},
        )
        assert resp.status_code == 503
        assert captured.get("path"), "spy did not capture a temp path"
        assert not Path(captured["path"]).exists()

    def test_temp_file_removed_on_transcribe_failure(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        reset_model_cache,
    ):
        model = _FakeModel(raise_exc=RuntimeError("boom"))
        monkeypatch.setattr(transcribe_module, "_get_model", lambda: model)

        resp = client.post(
            "/api/transcribe",
            files={"file": ("voice.webm", b"x", "audio/webm")},
        )
        assert resp.status_code == 500
        assert model.last_path is not None
        assert not Path(model.last_path).exists()


# ── Tests: filename / extension handling ──────────────────────────────────

class TestFilenameHandling:
    """The route preserves the original extension or falls back to .webm."""

    @pytest.mark.parametrize("filename,expected_suffix", [
        ("voice.webm", ".webm"),
        ("clip.mp4", ".mp4"),
        ("audio.wav", ".wav"),
        ("recording.ogg", ".ogg"),
        ("noext", ".webm"),       # no extension → fallback
    ])
    def test_temp_file_extension(
        self,
        client: TestClient,
        fake_model: _FakeModel,
        filename: str,
        expected_suffix: str,
    ):
        resp = client.post(
            "/api/transcribe",
            files={"file": (filename, b"audio-bytes", "audio/webm")},
        )
        assert resp.status_code == 200
        assert fake_model.last_path is not None
        assert fake_model.last_path.endswith(expected_suffix), (
            f"Expected temp path to end with {expected_suffix!r}, "
            f"got {fake_model.last_path!r}"
        )


# ── Tests: model lazy-load contract ───────────────────────────────────────

class TestModelLazyLoad:
    """The model is loaded once on first call and reused thereafter."""

    def test_model_only_loaded_once(self, monkeypatch: pytest.MonkeyPatch, reset_model_cache):
        load_count = {"n": 0}
        fake = _FakeModel()

        def fake_loader(*_args, **_kwargs):
            load_count["n"] += 1
            return fake

        # Patch the WhisperModel constructor inside the lazy loader.
        import faster_whisper
        monkeypatch.setattr(faster_whisper, "WhisperModel", fake_loader)

        # Two consecutive calls — only one load.
        m1 = transcribe_module._get_model()
        m2 = transcribe_module._get_model()
        assert m1 is m2 is fake
        assert load_count["n"] == 1

    def test_model_load_failure_does_not_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
        reset_model_cache,
    ):
        import faster_whisper

        def always_fails(*_args, **_kwargs):
            raise RuntimeError("init failed")

        monkeypatch.setattr(faster_whisper, "WhisperModel", always_fails)

        with pytest.raises(RuntimeError):
            transcribe_module._get_model()

        # On retry the loader runs again (no negative caching).
        with pytest.raises(RuntimeError):
            transcribe_module._get_model()


# ── Sanity: env override ─────────────────────────────────────────────────-

def test_default_model_name_is_base():
    """Production default — guard against accidental change to a heavy model."""
    # Read directly from os.environ to avoid import-time freeze.
    env_override = os.getenv("WHISPER_MODEL")
    if env_override:
        pytest.skip(f"WHISPER_MODEL is set to {env_override!r}, default is overridden")
    assert transcribe_module._MODEL_NAME == "base"
    assert transcribe_module._COMPUTE_TYPE == "int8"
