from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Any

import requests

from .analytics import VideoPerformance

# Metrics the Analytics API reports.query endpoint supports for dimensions=video.
# Thumbnail impressions and CTR are not available here; they only exist in the
# YouTube Reporting API "reach" bulk reports and in YouTube Studio exports, so
# they come in through load_ctr_csv() instead.
METRICS = (
    "views",
    "likes",
    "comments",
    "shares",
    "subscribersGained",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
)

_FIELD_BY_METRIC = {
    "views": ("views", int),
    "likes": ("likes", int),
    "comments": ("comments", int),
    "shares": ("shares", int),
    "subscribersGained": ("subscribers_gained", int),
    "estimatedMinutesWatched": ("estimated_minutes_watched", float),
    "averageViewDuration": ("average_view_duration_seconds", float),
    "averageViewPercentage": ("average_percentage_viewed", float),
}


class AnalyticsError(RuntimeError):
    """YouTube Analytics data could not be fetched or read."""


def parse_iso_duration(value: str) -> int | None:
    """ISO 8601 duration (e.g. PT1H2M3S) to seconds."""
    match = re.fullmatch(
        r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?",
        (value or "").strip(),
    )
    if not match or not any(match.groups()):
        return None
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


def _error_message(response: requests.Response) -> str:
    try:
        return response.json().get("error", {}).get("message", "") or response.reason
    except ValueError:
        return response.reason


class YouTubeAnalyticsAdapter:
    """Fetch the authenticated channel's per-video performance.

    Needs an OAuth access token with the yt-analytics.readonly scope in
    YOUTUBE_ACCESS_TOKEN. Titles and durations come from the Data API, using
    YOUTUBE_API_KEY when set and the access token otherwise.
    """

    ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
    VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, access_token: str | None = None, api_key: str | None = None) -> None:
        self.access_token = access_token or os.getenv("YOUTUBE_ACCESS_TOKEN")
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")

    def fetch_recent(
        self,
        start_date: str,
        end_date: str,
        max_results: int = 200,
    ) -> list[VideoPerformance]:
        if not self.access_token:
            raise AnalyticsError(
                "YOUTUBE_ACCESS_TOKEN is not set. Create an OAuth token with the "
                "yt-analytics.readonly scope for your channel."
            )

        response = requests.get(
            self.ANALYTICS_URL,
            params={
                "ids": "channel==MINE",
                "startDate": start_date,
                "endDate": end_date,
                "metrics": ",".join(METRICS),
                "dimensions": "video",
                "sort": "-views",
                # Required with dimensions=video; 200 is the API maximum.
                "maxResults": max(1, min(200, max_results)),
            },
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=30,
        )
        if not response.ok:
            raise AnalyticsError(
                f"YouTube Analytics returned {response.status_code}: {_error_message(response)}"
            )

        data = response.json()
        columns = [header.get("name") for header in data.get("columnHeaders", [])]
        videos: list[VideoPerformance] = []
        for row in data.get("rows", []):
            values = dict(zip(columns, row))
            video = VideoPerformance(video_id=str(values.get("video", "")), title="")
            for metric, (attr, cast) in _FIELD_BY_METRIC.items():
                if values.get(metric) is not None:
                    setattr(video, attr, cast(values[metric]))
            videos.append(video)

        self._attach_details(videos)
        return videos

    def _attach_details(self, videos: list[VideoPerformance]) -> None:
        """Fill real titles and durations from the Data API."""
        by_id = {video.video_id: video for video in videos if video.video_id}
        ids = list(by_id)
        for start in range(0, len(ids), 50):
            params: dict[str, Any] = {
                "part": "snippet,contentDetails",
                "id": ",".join(ids[start:start + 50]),
            }
            headers = {}
            if self.api_key:
                params["key"] = self.api_key
            else:
                headers["Authorization"] = f"Bearer {self.access_token}"

            try:
                response = requests.get(self.VIDEOS_URL, params=params, headers=headers, timeout=30)
            except requests.RequestException as exc:
                for video_id in ids[start:start + 50]:
                    by_id[video_id].metadata["details_error"] = type(exc).__name__
                continue
            if not response.ok:
                for video_id in ids[start:start + 50]:
                    by_id[video_id].metadata["details_error"] = str(response.status_code)
                continue

            for item in response.json().get("items", []):
                video = by_id.get(item.get("id"))
                if not video:
                    continue
                video.title = item.get("snippet", {}).get("title", "")
                video.duration_seconds = parse_iso_duration(
                    item.get("contentDetails", {}).get("duration", "")
                )


_ID_COLUMNS = ("video_id", "content", "video")
_IMPRESSION_COLUMNS = ("video_thumbnail_impressions", "impressions")
_CTR_COLUMNS = ("video_thumbnail_impressions_ctr", "impressions click-through rate (%)")


def _find_column(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {name.strip().lower(): name for name in fieldnames}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def _number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def load_ctr_csv(path: str | Path) -> dict[str, dict[str, float]]:
    """Read thumbnail impressions and CTR per video from a CSV.

    Accepts a YouTube Studio "Table data.csv" export (Content, Impressions,
    Impressions click-through rate (%)) or a Reporting API reach report
    (video_id, video_thumbnail_impressions, video_thumbnail_impressions_ctr).
    Daily rows are combined per video. CTR is returned in percent.
    """
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        id_col = _find_column(fieldnames, _ID_COLUMNS)
        impressions_col = _find_column(fieldnames, _IMPRESSION_COLUMNS)
        ctr_col = _find_column(fieldnames, _CTR_COLUMNS)
        if not (id_col and impressions_col and ctr_col):
            raise AnalyticsError(
                "CSV needs a video id column (video_id or Content), an impressions "
                "column and a CTR column; found: " + ", ".join(fieldnames)
            )
        rows = [
            (
                str(row.get(id_col, "")).strip(),
                _number(row.get(impressions_col)),
                _number(row.get(ctr_col)),
            )
            for row in reader
        ]

    rows = [
        (video_id, impressions, ctr)
        for video_id, impressions, ctr in rows
        if video_id and video_id.lower() != "total" and impressions is not None and ctr is not None
    ]
    # Studio exports use percent; reach reports may use a 0-1 ratio.
    ratio = bool(rows) and all(ctr <= 1 for _, _, ctr in rows) and "(%)" not in ctr_col
    totals: dict[str, list[float]] = {}
    for video_id, impressions, ctr in rows:
        percent = ctr * 100 if ratio else ctr
        bucket = totals.setdefault(video_id, [0.0, 0.0])
        bucket[0] += impressions
        bucket[1] += impressions * percent / 100

    return {
        video_id: {
            "impressions": int(impressions),
            "ctr": round(clicks / impressions * 100, 2) if impressions else 0.0,
        }
        for video_id, (impressions, clicks) in totals.items()
    }


def apply_ctr(videos: list[VideoPerformance], ctr_by_video: dict[str, dict[str, float]]) -> int:
    """Copy CSV impressions and CTR onto matching videos; returns how many matched."""
    matched = 0
    for video in videos:
        values = ctr_by_video.get(video.video_id)
        if values:
            video.impressions = int(values["impressions"])
            video.ctr = float(values["ctr"])
            matched += 1
    return matched
