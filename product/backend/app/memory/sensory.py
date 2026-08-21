"""Sensory memory — per-user in-memory ring buffer of recent UI events.

Not persisted. TTL ~30 minutes. Survives within a single backend process.
Used to let the assistant reference very recent context without forcing
the user to repeat themselves (e.g. "the resume you just uploaded").
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock

_TTL_SECONDS = 30 * 60       # 30 minutes
_RING_SIZE = 10              # last 10 events per user


@dataclass
class SensoryEvent:
    kind: str               # e.g. "upload_resume", "view_candidate", "send_email"
    summary: str            # one-line human-readable
    ts: float               # unix timestamp


class SensoryBuffer:
    """Per-user ring buffer. Thread-safe."""

    def __init__(self):
        self._buffers: dict[str, deque[SensoryEvent]] = {}
        self._lock = Lock()

    def add(self, user_id: str, kind: str, summary: str) -> None:
        if not user_id:
            return
        with self._lock:
            buf = self._buffers.setdefault(user_id, deque(maxlen=_RING_SIZE))
            buf.append(SensoryEvent(kind=kind, summary=summary, ts=time.time()))

    def recent(self, user_id: str, limit: int = 5) -> list[SensoryEvent]:
        if not user_id:
            return []
        cutoff = time.time() - _TTL_SECONDS
        with self._lock:
            buf = self._buffers.get(user_id)
            if not buf:
                return []
            fresh = [e for e in buf if e.ts >= cutoff]
        return fresh[-limit:]

    def clear(self, user_id: str) -> None:
        with self._lock:
            self._buffers.pop(user_id, None)


# Module-level singleton — one buffer for the whole process.
_BUFFER = SensoryBuffer()


def emit_event(user_id: str, kind: str, summary: str) -> None:
    _BUFFER.add(user_id, kind, summary)


def recent_events(user_id: str, limit: int = 5) -> list[SensoryEvent]:
    return _BUFFER.recent(user_id, limit)
