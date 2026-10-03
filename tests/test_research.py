import io
import json
import urllib.error
from pathlib import Path

import pytest

import src.research as research
from src.research import (
    ResearchAgent,
    YouTubeAPIError,
    YouTubeQuotaError,
    normalize_channel_url,
)


def test_research_agent_reads_text_files(tmp_path: Path, config):
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "example.md").write_text("# Example topic\nSome evidence.", encoding="utf-8")
    (research_dir / "README.md").write_text("# Research Inputs\nHow to use this folder.", encoding="utf-8")

    items = ResearchAgent(config, str(research_dir)).collect()

    assert [item.title for item in items] == ["Example topic"]


@pytest.mark.parametrize("raw,expected", [
    ("@chef", "https://www.youtube.com/@chef"),
    ("youtube.com/@chef", "https://youtube.com/@chef"),
    ("https://www.youtube.com/@chef", "https://www.youtube.com/@chef"),
])
def test_normalize_channel_url(raw, expected):
    assert normalize_channel_url(raw) == expected


def _agent(config, monkeypatch, responses):
    calls = []

    def fake_get_json(url):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(ResearchAgent, "_get_json", staticmethod(fake_get_json))
    return ResearchAgent(config), calls


def test_resolve_handle_without_scheme(config, monkeypatch):
    agent, calls = _agent(config, monkeypatch, [{"items": [{"id": "UC_handle"}]}])

    assert agent._resolve_channel_id("youtube.com/@chef/videos") == "UC_handle"
    assert "forHandle=%40chef" in calls[0]


def test_resolve_channel_url_needs_no_api_call(config, monkeypatch):
    agent, calls = _agent(config, monkeypatch, [])

    assert agent._resolve_channel_id("https://www.youtube.com/channel/UC_direct/featured") == "UC_direct"
    assert calls == []


def test_resolve_custom_c_url_searches(config, monkeypatch):
    agent, calls = _agent(config, monkeypatch, [{"items": [{"id": {"channelId": "UC_custom"}}]}])

    assert agent._resolve_channel_id("https://www.youtube.com/c/MyKitchen") == "UC_custom"
    assert "/search?" in calls[0] and "type=channel" in calls[0]


def test_resolve_rejects_other_sites(config, monkeypatch):
    agent, _ = _agent(config, monkeypatch, [])
    with pytest.raises(ValueError):
        agent._resolve_channel_id("https://vimeo.com/chef")


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _http_error(code, reason=""):
    body = json.dumps({"error": {"message": "nope", "errors": [{"reason": reason}]}}).encode()
    return urllib.error.HTTPError("https://example.test/?key=SECRET", code, "Error", {}, io.BytesIO(body))


def _urlopen_sequence(monkeypatch, outcomes):
    calls = []

    def fake_urlopen(request, timeout=20):
        calls.append(request.full_url)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(json.dumps(outcome).encode())

    monkeypatch.setattr(research.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(research.time, "sleep", lambda seconds: None)
    return calls


def test_get_json_retries_server_errors(monkeypatch):
    calls = _urlopen_sequence(monkeypatch, [_http_error(503), {"items": [1]}])

    assert ResearchAgent._get_json("https://example.test/") == {"items": [1]}
    assert len(calls) == 2


def test_get_json_stops_on_quota(monkeypatch):
    calls = _urlopen_sequence(monkeypatch, [_http_error(403, "quotaExceeded")])

    with pytest.raises(YouTubeQuotaError):
        ResearchAgent._get_json("https://example.test/")
    assert len(calls) == 1


def test_get_json_error_does_not_leak_key(monkeypatch):
    _urlopen_sequence(monkeypatch, [_http_error(400, "badRequest")])

    with pytest.raises(YouTubeAPIError) as excinfo:
        ResearchAgent._get_json("https://example.test/?key=SECRET")
    assert "SECRET" not in str(excinfo.value)
    assert "400" in str(excinfo.value)


def test_get_json_gives_up_after_retries(monkeypatch):
    error = urllib.error.URLError("offline")
    calls = _urlopen_sequence(monkeypatch, [error, error, error])

    with pytest.raises(YouTubeAPIError):
        ResearchAgent._get_json("https://example.test/")
    assert len(calls) == research.RETRY_ATTEMPTS
