from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import ChannelConfig, ResearchItem


class ResearchAgent:
    """Research foundation.

    Local Markdown/text research is supported first. Live source adapters can
    later return the same ResearchItem objects.
    """

    def __init__(self, config: ChannelConfig, research_root: str = "research") -> None:
        self.config = config
        self.research_root = Path(research_root)

    def collect(self) -> list[ResearchItem]:
        if not self.research_root.exists():
            return []

        items: list[ResearchItem] = []

        for path in sorted(self.research_root.rglob("*")):
            if path.suffix.lower() not in {".md", ".txt"}:
                continue

            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue

            title = next(
                (
                    line.lstrip("#").strip()
                    for line in text.splitlines()
                    if line.strip()
                ),
                path.stem,
            )

            items.append(
                ResearchItem(
                    source=path.parent.name,
                    title=title,
                    summary=text[:1200],
                    topics=[self.config.niche],
                    metadata={"path": str(path)},
                )
            )

        return items

    @staticmethod
    def normalize(items: Iterable[ResearchItem]) -> list[ResearchItem]:
        seen: set[tuple[str, str]] = set()
        normalized: list[ResearchItem] = []

        for item in items:
            key = (item.source.lower(), item.title.lower())
            if key in seen:
                continue

            seen.add(key)
            normalized.append(item)

        return normalized
