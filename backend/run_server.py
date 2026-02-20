"""Entry point for the PyInstaller-bundled backend.

Usage:  backend.exe <port>      (packaged)
        python run_server.py 8000   (dev testing)
"""

import os
import sys


def _configure_bundled_paths():
    """When running inside a PyInstaller bundle, redirect model/cache paths."""
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return

    # Writable cache for any runtime downloads
    data_dir = os.environ.get("OPEN_RECRUITER_DATA_DIR", "")
    if data_dir:
        cache_dir = os.path.join(data_dir, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ.setdefault("HF_HOME", cache_dir)


if __name__ == "__main__":
    _configure_bundled_paths()

    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
