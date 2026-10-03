from __future__ import annotations

import re
import urllib.parse
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from .learning import PerformanceMemory
from .output import data_path, dump_json, load_json, now_iso

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class MemoryStore:
    """JSON-backed channel memory in data/channel_memory.json."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else data_path("channel_memory.json")

    def save(self, memory: PerformanceMemory) -> None:
        dump_json(self.path, asdict(memory))

    def load(self) -> PerformanceMemory:
        data = load_json(self.path, {}) or {}
        names = {item.name for item in fields(PerformanceMemory)}
        return PerformanceMemory(**{key: value for key, value in data.items() if key in names})


def parse_video_id(value: str) -> str:
    """Accept a bare video ID or a youtube.com / youtu.be URL."""
    value = value.strip()
    if VIDEO_ID.match(value):
        return value

    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc.lower()
    candidate = ""
    if host.endswith("youtu.be"):
        candidate = parsed.path.strip("/").split("/")[0]
    elif "youtube.com" in host:
        query = urllib.parse.parse_qs(parsed.query)
        if "v" in query:
            candidate = query["v"][0]
        else:
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"}:
                candidate = parts[1]

    if VIDEO_ID.match(candidate):
        return candidate
    raise ValueError(f"Not a YouTube video ID or URL: {value}")


class PublishedRegistry:
    """data/published.json: which opportunity each published video came from.

    This link is what lets the learning loop attribute a video's performance
    to the topic it was made for.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else data_path("published.json")

    def load(self) -> list[dict[str, Any]]:
        return load_json(self.path, []) or []

    def record(
        self,
        video_id: str,
        opportunity_id: str,
        topic: str,
        title: str,
        run_id: str,
    ) -> dict[str, Any]:
        entry = {
            "video_id": video_id,
            "opportunity_id": opportunity_id,
            "topic": topic,
            "title": title,
            "run_id": run_id,
            "recorded_at": now_iso(),
        }
        entries = [item for item in self.load() if item.get("video_id") != video_id]
        entries.append(entry)
        dump_json(self.path, entries)
        return entry

    def topic_by_video(self) -> dict[str, str]:
        return {
            item["video_id"]: item.get("topic", "")
            for item in self.load()
            if item.get("video_id")
        }
