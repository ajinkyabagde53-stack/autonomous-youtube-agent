from __future__ import annotations

import os
from typing import Any

import requests

from .analytics import VideoPerformance


class YouTubeAnalyticsAdapter:
    """Adapter boundary for authenticated YouTube Analytics data.

    OAuth credentials are intentionally not hard-coded. The first production
    implementation should use a secure OAuth flow and store refresh tokens
    outside the repository.
    """

    ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token or os.getenv("YOUTUBE_ACCESS_TOKEN")

    def fetch_recent(self, start_date: str, end_date: str) -> list[VideoPerformance]:
        if not self.access_token:
            return []

        params: dict[str, Any] = {
            "ids": "channel==MINE",
            "startDate": start_date,
            "endDate": end_date,
            "metrics": "views,likes,comments,subscribersGained,averageViewDuration,averageViewPercentage,impressions,impressionsCtr",
            "dimensions": "video",
            "sort": "-views",
        }

        response = requests.get(
            self.ANALYTICS_URL,
            params=params,
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        rows = data.get("rows", [])
        videos: list[VideoPerformance] = []

        for row in rows:
            videos.append(
                VideoPerformance(
                    video_id=str(row[0]),
                    title=str(row[0]),
                    views=int(row[1] or 0),
                    likes=int(row[2] or 0),
                    comments=int(row[3] or 0),
                    subscribers_gained=int(row[4] or 0),
                    average_view_duration_seconds=float(row[5] or 0),
                    average_percentage_viewed=float(row[6] or 0),
                    impressions=int(row[7] or 0),
                    ctr=float(row[8] or 0),
                )
            )

        return videos
