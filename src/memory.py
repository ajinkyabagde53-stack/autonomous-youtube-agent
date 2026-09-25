from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .learning import PerformanceMemory


class MemoryStore:
    """Simple JSON-backed memory store for the channel learning loop."""

    def __init__(self, path: str = "outputs/channel_memory.json") -> None:
        self.path = Path(path)

    def save(self, memory: PerformanceMemory) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(memory), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self) -> PerformanceMemory:
        if not self.path.exists():
            return PerformanceMemory()

        data = json.loads(self.path.read_text(encoding="utf-8"))
        return PerformanceMemory(
            topic_signals=data.get("topic_signals", {}),
            format_signals=data.get("format_signals", {}),
            title_signals=data.get("title_signals", {}),
        )
