from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

MODEL_ENDPOINT: Final = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"
ERROR_LOG_PATH: Final = Path(__file__).with_name("gemini_errors.log")


def get_api_key() -> str | None:
    k = os.getenv("GOOGLE_API_KEY")
    if k:
        return k.strip()
    p = Path(__file__).with_name("api_key.txt")
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


def log_error(message: str) -> None:
    """Append a timestamped Gemini error message to the shared log file."""

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    entry = f"[{timestamp}] {message}\n"
    try:
        ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ERROR_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(entry)
    except Exception:
        # Logging failures should never interfere with gameplay, so swallow them.
        pass
