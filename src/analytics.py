from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoPerformance:
    video_id: str
    title: str
    impressions: int | None = None
    ctr: float | None = None
    views: int | None = None
    average_view_duration_seconds: float | None = None
    average_percentage_viewed: float | None = None
    likes: int | None = None
    comments: int | None = None
    subscribers_gained: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AnalyticsAgent:
    """Foundation for the channel feedback loop."""

    def summarize(self, videos: list[VideoPerformance]) -> dict[str, Any]:
        if not videos:
            return {"videos": 0, "signals": []}

        ctr_values = [v.ctr for v in videos if v.ctr is not None]
        retention_values = [
            v.average_percentage_viewed
            for v in videos
            if v.average_percentage_viewed is not None
        ]

        return {
            "videos": len(videos),
            "average_ctr": round(sum(ctr_values) / len(ctr_values), 4) if ctr_values else None,
            "average_percentage_viewed": round(sum(retention_values) / len(retention_values), 4) if retention_values else None,
            "signals": [
                {
                    "video_id": v.video_id,
                    "title": v.title,
                    "ctr": v.ctr,
                    "retention": v.average_percentage_viewed,
                    "views": v.views,
                }
                for v in videos
            ],
        }
