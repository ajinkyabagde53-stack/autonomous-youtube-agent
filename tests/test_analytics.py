import pytest

import src.youtube_analytics as yta
from src.analytics import AnalyticsAgent, VideoPerformance
from src.youtube_analytics import (
    AnalyticsError,
    YouTubeAnalyticsAdapter,
    apply_ctr,
    load_ctr_csv,
    parse_iso_duration,
)


@pytest.mark.parametrize("value,seconds", [
    ("PT45S", 45),
    ("PT8M3S", 483),
    ("PT1H2M", 3720),
    ("P1DT1S", 86401),
    ("", None),
    ("garbage", None),
])
def test_parse_iso_duration(value, seconds):
    assert parse_iso_duration(value) == seconds


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.ok = status < 400
        self.reason = "Bad Request" if status >= 400 else "OK"

    def json(self):
        return self._payload


def test_fetch_recent_maps_columns_and_attaches_titles(monkeypatch):
    calls = []
    analytics_payload = {
        "columnHeaders": [{"name": "video"}, {"name": "views"}, {"name": "averageViewPercentage"}],
        "rows": [["dQw4w9WgXcQ", 1200, 47.5]],
    }
    videos_payload = {"items": [{
        "id": "dQw4w9WgXcQ",
        "snippet": {"title": "How to bake bread"},
        "contentDetails": {"duration": "PT9M"},
    }]}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, headers))
        return _Resp(analytics_payload if "youtubeanalytics" in url else videos_payload)

    monkeypatch.setattr(yta.requests, "get", fake_get)
    [video] = YouTubeAnalyticsAdapter(access_token="token", api_key="key").fetch_recent("2026-09-01", "2026-09-30")

    assert video.views == 1200
    assert video.average_percentage_viewed == 47.5
    assert video.title == "How to bake bread"
    assert video.duration_seconds == 540
    params = calls[0][1]
    assert params["maxResults"] == 200
    assert "impressions" not in params["metrics"]
    assert calls[1][1]["key"] == "key"


def test_fetch_recent_requires_token():
    with pytest.raises(AnalyticsError):
        YouTubeAnalyticsAdapter().fetch_recent("2026-09-01", "2026-09-30")


def test_fetch_recent_reports_api_errors(monkeypatch):
    monkeypatch.setattr(
        yta.requests,
        "get",
        lambda *a, **k: _Resp({"error": {"message": "Unknown identifier"}}, status=400),
    )
    with pytest.raises(AnalyticsError, match="Unknown identifier"):
        YouTubeAnalyticsAdapter(access_token="token").fetch_recent("2026-09-01", "2026-09-30")


def test_load_ctr_csv_from_studio_export(tmp_path):
    path = tmp_path / "Table data.csv"
    path.write_text(
        "﻿Content,Video title,Impressions,Impressions click-through rate (%)\n"
        "Total,,3000,5.0\n"
        "dQw4w9WgXcQ,Bread,2000,6.5\n"
        "abcdefghijk,Pasta,\"1,000\",2.0\n",
        encoding="utf-8",
    )

    data = load_ctr_csv(path)

    assert data == {
        "dQw4w9WgXcQ": {"impressions": 2000, "ctr": 6.5},
        "abcdefghijk": {"impressions": 1000, "ctr": 2.0},
    }


def test_load_ctr_csv_from_reach_report_combines_days(tmp_path):
    path = tmp_path / "reach.csv"
    path.write_text(
        "date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n"
        "20260901,UC1,dQw4w9WgXcQ,1000,0.05\n"
        "20260902,UC1,dQw4w9WgXcQ,3000,0.03\n",
        encoding="utf-8",
    )

    data = load_ctr_csv(path)

    # (1000 * 5% + 3000 * 3%) / 4000 = 3.5%
    assert data == {"dQw4w9WgXcQ": {"impressions": 4000, "ctr": 3.5}}


def test_load_ctr_csv_rejects_unknown_columns(tmp_path):
    path = tmp_path / "other.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(AnalyticsError):
        load_ctr_csv(path)


def test_apply_ctr_and_summary():
    videos = [VideoPerformance(video_id="dQw4w9WgXcQ", title="Bread", views=10), VideoPerformance(video_id="x", title="", views=5)]

    assert apply_ctr(videos, {"dQw4w9WgXcQ": {"impressions": 100, "ctr": 4.0}}) == 1
    summary = AnalyticsAgent().summarize(videos)
    assert summary["average_ctr"] == 4.0
    assert summary["total_views"] == 15
