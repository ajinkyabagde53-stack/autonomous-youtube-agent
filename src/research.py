from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

from .models import ChannelConfig, ReferenceChannel, ResearchItem

RETRY_ATTEMPTS = 3
RETRY_STATUS = {429, 500, 502, 503, 504}
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded"}


class YouTubeAPIError(RuntimeError):
    """The YouTube Data API rejected a request."""


class YouTubeQuotaError(YouTubeAPIError):
    """The daily YouTube Data API quota is used up; further calls will fail too."""


def normalize_channel_url(value: str) -> str:
    """Accept @handles and URLs pasted without https://."""
    value = value.strip()
    if value.startswith("@"):
        return f"https://www.youtube.com/{value}"
    if not value.lower().startswith(("http://", "https://")):
        return f"https://{value}"
    return value


def _api_error(exc: urllib.error.HTTPError) -> YouTubeAPIError:
    """Turn an HTTPError into a readable error without echoing the request URL."""
    reason, message = "", ""
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        error = payload.get("error", {})
        message = error.get("message", "")
        reason = (error.get("errors") or [{}])[0].get("reason", "")
    except (ValueError, AttributeError, OSError):
        pass

    if reason in QUOTA_REASONS and exc.code in {403, 429}:
        return YouTubeQuotaError(
            "YouTube Data API quota is exhausted for today (it resets at midnight "
            "Pacific time). Try again later or raise the quota in Google Cloud Console."
        )
    detail = message or exc.reason
    return YouTubeAPIError(f"YouTube API returned {exc.code}: {detail}")


class ResearchAgent:
    """Collect research from user-selected reference channels.

    The channels define the research territory. A separate intelligence step
    can infer the territory before broader YouTube validation is performed.
    """

    def __init__(self, config: ChannelConfig, research_root: str = "research") -> None:
        self.config = config
        self.research_root = Path(research_root)

    def collect(self, genre: str | None = None) -> list[ResearchItem]:
        """Collect optional local research.

        Kept for backwards compatibility. Live channel research is the primary
        source when reference channels are supplied.
        """
        selected_genre = (genre or self.config.niche).strip()
        if not self.research_root.exists():
            return []

        items: list[ResearchItem] = []
        for path in sorted(self.research_root.rglob("*")):
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            if path.name.lower() == "readme.md":
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

    def collect_reference_channel(
        self,
        channel_url: str,
        max_videos: int = 50,
        region_code: str = "US",
    ) -> tuple[ReferenceChannel, list[ResearchItem]]:
        """Resolve a channel URL and collect its recent public videos."""
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise RuntimeError("YOUTUBE_API_KEY is required for reference channel research.")

        channel_id = self._resolve_channel_id(channel_url)
        params = urllib.parse.urlencode({
            "part": "snippet,statistics,contentDetails,topicDetails",
            "id": channel_id,
            "key": api_key,
        })
        payload = self._get_json(
            f"https://www.googleapis.com/youtube/v3/channels?{params}"
        )
        channels = payload.get("items", [])
        if not channels:
            raise ValueError(f"Could not resolve YouTube channel: {channel_url}")

        channel = channels[0]
        snippet = channel.get("snippet", {})
        stats = channel.get("statistics", {})
        details = channel.get("contentDetails", {})
        topics = channel.get("topicDetails", {}).get("topicCategories", [])
        uploads_id = details.get("relatedPlaylists", {}).get("uploads", "")

        profile = ReferenceChannel(
            url=channel_url,
            channel_id=channel_id,
            title=snippet.get("title", ""),
            description=snippet.get("description", "")[:1500],
            subscriber_count=int(stats.get("subscriberCount", 0) or 0),
            video_count=int(stats.get("videoCount", 0) or 0),
            view_count=int(stats.get("viewCount", 0) or 0),
            country=snippet.get("country", ""),
            published_at=snippet.get("publishedAt", ""),
            uploads_playlist_id=uploads_id,
            topic_categories=topics,
        )

        videos = self._collect_channel_videos(
            uploads_id,
            channel_id,
            max_videos=max_videos,
        )
        return profile, videos

    def _collect_channel_videos(
        self,
        uploads_playlist_id: str,
        channel_id: str,
        max_videos: int = 50,
    ) -> list[ResearchItem]:
        if not uploads_playlist_id:
            return []

        api_key = os.getenv("YOUTUBE_API_KEY")
        items: list[dict] = []
        page_token = ""

        while len(items) < max_videos:
            params = {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": min(50, max_videos - len(items)),
                "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            payload = self._get_json(
                "https://www.googleapis.com/youtube/v3/playlistItems?"
                + urllib.parse.urlencode(params)
            )
            items.extend(payload.get("items", []))
            page_token = payload.get("nextPageToken", "")
            if not page_token:
                break

        video_ids = [
            item.get("contentDetails", {}).get("videoId")
            for item in items
            if item.get("contentDetails", {}).get("videoId")
        ][:max_videos]

        if not video_ids:
            return []

        stats_payload = self._get_json(
            "https://www.googleapis.com/youtube/v3/videos?"
            + urllib.parse.urlencode({
                "part": "snippet,statistics,contentDetails,topicDetails",
                "id": ",".join(video_ids),
                "key": api_key,
            })
        )
        stats_by_id = {item.get("id"): item for item in stats_payload.get("items", [])}

        results: list[ResearchItem] = []
        for item in items[:max_videos]:
            video_id = item.get("contentDetails", {}).get("videoId")
            if not video_id:
                continue

            video = stats_by_id.get(video_id, {})
            snippet = video.get("snippet", item.get("snippet", {}))
            stats = video.get("statistics", {})
            topic_categories = video.get("topicDetails", {}).get("topicCategories", [])

            results.append(
                ResearchItem(
                    source=f"youtube:{channel_id}",
                    title=snippet.get("title", "Untitled video"),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    summary=snippet.get("description", "")[:1200],
                    topics=[],
                    metadata={
                        "channel_id": channel_id,
                        "video_id": video_id,
                        "published_at": snippet.get("publishedAt", ""),
                        "view_count": int(stats.get("viewCount", 0) or 0),
                        "like_count": int(stats.get("likeCount", 0) or 0),
                        "comment_count": int(stats.get("commentCount", 0) or 0),
                        "duration": video.get("contentDetails", {}).get("duration", ""),
                        "category_id": snippet.get("categoryId", ""),
                        "topic_categories": topic_categories,
                    },
                )
            )

        return results

    def _resolve_channel_id(self, channel_url: str) -> str:
        parsed = urllib.parse.urlparse(normalize_channel_url(channel_url))
        host = parsed.netloc.lower()
        path = parsed.path.strip("/")

        if "youtube.com" not in host:
            raise ValueError("Please provide a YouTube channel URL.")

        if path.startswith("channel/"):
            return path.split("/")[1]

        if path.startswith("c/"):
            # Legacy custom URLs have no direct lookup; search for the channel.
            # A search costs 100 quota units, so @handles are preferred.
            name = urllib.parse.unquote(path.split("/")[1])
            params = urllib.parse.urlencode({
                "part": "snippet",
                "q": name,
                "type": "channel",
                "maxResults": 1,
                "key": os.getenv("YOUTUBE_API_KEY"),
            })
            payload = self._get_json(
                "https://www.googleapis.com/youtube/v3/search?" + params
            )
            for item in payload.get("items", []):
                channel_id = item.get("id", {}).get("channelId") or item.get("snippet", {}).get("channelId")
                if channel_id:
                    return channel_id

        if path.startswith("@"):
            handle = path.split("/", 1)[0]
            params = urllib.parse.urlencode({
                "part": "id",
                "forHandle": handle,
                "key": os.getenv("YOUTUBE_API_KEY"),
            })
            payload = self._get_json(
                "https://www.googleapis.com/youtube/v3/channels?" + params
            )
            if payload.get("items"):
                return payload["items"][0]["id"]

        if path.startswith("user/"):
            username = path.split("/")[1]
            params = urllib.parse.urlencode({
                "part": "id",
                "forUsername": username,
                "key": os.getenv("YOUTUBE_API_KEY"),
            })
            payload = self._get_json(
                "https://www.googleapis.com/youtube/v3/channels?" + params
            )
            if payload.get("items"):
                return payload["items"][0]["id"]

        raise ValueError(
            "Could not resolve the channel URL. Use a YouTube @handle, /channel/, "
            "/user/ or /c/ URL."
        )

    def collect_youtube(
        self,
        territory: str,
        region_code: str = "US",
        max_results: int = 25,
    ) -> list[ResearchItem]:
        """Validate an inferred territory against the wider YouTube landscape."""
        territory = territory.strip()
        if not territory:
            return []
        return self.collect_queries(
            [territory, f"{territory} how to", f"{territory} explained"],
            label=territory,
            region_code=region_code,
            max_results=max_results,
        )

    def collect_queries(
        self,
        queries: list[str],
        label: str,
        region_code: str = "US",
        max_results: int = 25,
    ) -> list[ResearchItem]:
        """Search YouTube for each query and return up to max_results videos.

        Results are interleaved across queries so the first query cannot crowd
        out the others. Each search costs 100 quota units.
        """
        api_key = os.getenv("YOUTUBE_API_KEY")
        queries = [query.strip() for query in queries if query.strip()]
        if not api_key or not queries or max_results <= 0:
            return []

        per_query = max(5, min(25, max_results // len(queries) + 1))
        results_by_query: list[list[tuple[str, dict]]] = []
        for query in queries:
            params = urllib.parse.urlencode({
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": per_query,
                "order": "relevance",
                "regionCode": region_code,
                "relevanceLanguage": "en",
                "safeSearch": "moderate",
                "key": api_key,
            })
            payload = self._get_json(
                f"https://www.googleapis.com/youtube/v3/search?{params}"
            )
            results_by_query.append([
                (query, result)
                for result in payload.get("items", [])
                if result.get("id", {}).get("videoId")
            ])

        found: dict[str, tuple[str, dict]] = {}
        for rank in range(per_query):
            for results in results_by_query:
                if rank < len(results):
                    query, result = results[rank]
                    found.setdefault(result["id"]["videoId"], (query, result))

        ids = list(found)[:max_results]
        if not ids:
            return []

        params = urllib.parse.urlencode({
            "part": "snippet,statistics",
            "id": ",".join(ids),
            "key": api_key,
        })
        stats_payload = self._get_json(
            f"https://www.googleapis.com/youtube/v3/videos?{params}"
        )
        stats_by_id = {
            item.get("id"): item for item in stats_payload.get("items", [])
        }

        items: list[ResearchItem] = []
        for video_id in ids:
            query, result = found[video_id]
            snippet = result.get("snippet", {})
            stats = stats_by_id.get(video_id, {}).get("statistics", {})
            items.append(
                ResearchItem(
                    source="youtube",
                    title=snippet.get("title", "Untitled video"),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    summary=snippet.get("description", "")[:1200],
                    topics=[label],
                    metadata={
                        "territory": label,
                        "query": query,
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
        """GET a YouTube API URL, retrying transient failures with backoff."""
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Overseer/1.0"},
        )
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                error = _api_error(exc)
                if isinstance(error, YouTubeQuotaError) or exc.code not in RETRY_STATUS:
                    raise error from None
                if attempt == RETRY_ATTEMPTS:
                    raise error from None
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == RETRY_ATTEMPTS:
                    raise YouTubeAPIError(f"Could not reach the YouTube API: {exc}") from None
            time.sleep(2 ** (attempt - 1))
        raise YouTubeAPIError("YouTube API request failed.")

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
