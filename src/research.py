from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

from .models import ChannelConfig, ResearchItem


class ResearchAgent:
    """Research a user-selected genre.

    Local Markdown/text research is always supported. If YOUTUBE_API_KEY is
    configured, the agent also pulls a focused sample from YouTube so the
    opportunity engine can reason about demand and competition inside the
    selected genre rather than the whole channel niche.
    """

    def __init__(self, config: ChannelConfig, research_root: str = "research") -> None:
        self.config = config
        self.research_root = Path(research_root)

    def collect(self, genre: str | None = None) -> list[ResearchItem]:
        selected_genre = (genre or self.config.niche).strip()
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
                    topics=[selected_genre],
                    metadata={"path": str(path), "genre": selected_genre},
                )
            )

        return items

    def collect_youtube(
        self,
        genre: str,
        region_code: str = "US",
        max_results: int = 25,
    ) -> list[ResearchItem]:
        """Collect a small, quota-conscious YouTube sample for a genre.

        Three search queries are used to cover the genre, practical intent and
        workflow intent. YouTube's search.list costs 1 quota unit per request;
        one videos.list call enriches the returned IDs with view/like/comment
        counts.
        """
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return []

        genre = genre.strip()
        queries = [
            genre,
            f"{genre} how to",
            f"{genre} workflow",
        ]

        found: dict[str, dict] = {}
        per_query = max(5, min(25, max_results // len(queries) + 1))

        for query in queries:
            params = urllib.parse.urlencode(
                {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": per_query,
                    "order": "relevance",
                    "regionCode": region_code,
                    "relevanceLanguage": "en",
                    "safeSearch": "moderate",
                    "key": api_key,
                }
            )
            payload = self._get_json(
                f"https://www.googleapis.com/youtube/v3/search?{params}"
            )
            for result in payload.get("items", []):
                video_id = result.get("id", {}).get("videoId")
                if video_id:
                    found[video_id] = result

        ids = list(found)[:max_results]
        if not ids:
            return []

        params = urllib.parse.urlencode(
            {
                "part": "snippet,statistics",
                "id": ",".join(ids),
                "key": api_key,
            }
        )
        stats_payload = self._get_json(
            f"https://www.googleapis.com/youtube/v3/videos?{params}"
        )

        stats_by_id = {
            item.get("id"): item
            for item in stats_payload.get("items", [])
        }

        items: list[ResearchItem] = []
        for video_id in ids:
            result = found[video_id]
            snippet = result.get("snippet", {})
            stats = stats_by_id.get(video_id, {}).get("statistics", {})
            title = snippet.get("title", "Untitled video")
            url = f"https://www.youtube.com/watch?v={video_id}"

            items.append(
                ResearchItem(
                    source="youtube",
                    title=title,
                    url=url,
                    summary=snippet.get("description", "")[:1200],
                    topics=[genre],
                    metadata={
                        "genre": genre,
                        "video_id": video_id,
                        "channel_title": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "view_count": int(stats.get("viewCount", 0) or 0),
                        "like_count": int(stats.get("likeCount", 0) or 0),
                        "comment_count": int(stats.get("commentCount", 0) or 0),
                    },
                )
            )

        return items

    @staticmethod
    def _get_json(url: str) -> dict:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Overseer/1.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

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
