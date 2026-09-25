from __future__ import annotations

import os
from typing import Any

import requests

from .models import ChannelConfig, ResearchItem


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeResearchAgent:
    """YouTube Data API adapter.

    This adapter collects public video metadata. Transcript and LLM analysis
    remain separate stages so failures in one source do not break the pipeline.
    """

    def __init__(self, config: ChannelConfig, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")

    def search(self, queries: list[str], max_results_per_query: int = 10) -> list[ResearchItem]:
        if not self.api_key:
            return []

        results: list[ResearchItem] = []
        seen: set[str] = set()

        for query in queries:
            params: dict[str, Any] = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": min(max_results_per_query, 50),
                "order": "relevance",
                "key": self.api_key,
            }

            response = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=30)
            response.raise_for_status()

            for item in response.json().get("items", []):
                video_id = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if not video_id or video_id in seen:
                    continue

                seen.add(video_id)
                results.append(
                    ResearchItem(
                        source="youtube",
                        title=snippet.get("title", ""),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        summary=snippet.get("description", "")[:1500],
                        topics=[query],
                        metadata={
                            "video_id": video_id,
                            "channel_id": snippet.get("channelId"),
                            "channel_title": snippet.get("channelTitle"),
                            "published_at": snippet.get("publishedAt"),
                        },
                    )
                )

        return results

    @staticmethod
    def build_queries(config: ChannelConfig) -> list[str]:
        queries = [config.niche]
        queries.extend(config.audience.get("pain_points", []))
        queries.extend(config.content.get("pillars", []))
        return list(dict.fromkeys(q.strip() for q in queries if q.strip()))
