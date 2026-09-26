from __future__ import annotations

from datetime import datetime, timezone


def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "autonomous-youtube-agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
