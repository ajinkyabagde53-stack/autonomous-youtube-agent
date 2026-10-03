from __future__ import annotations

from typing import Any

from .models import ResearchItem


class TranscriptAgent:
    """Fetch transcripts when available.

    The transcript dependency is imported lazily so the rest of the research
    pipeline can still run when transcript retrieval is unavailable.
    """

    def enrich(self, items: list[ResearchItem]) -> list[ResearchItem]:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            return items

        api = YouTubeTranscriptApi()

        for item in items:
            video_id = item.metadata.get("video_id")
            if not video_id:
                continue

            try:
                fetched = api.fetch(video_id)
                snippets: list[str] = []
                for entry in fetched:
                    text = getattr(entry, "text", None)
                    if text is None and isinstance(entry, dict):
                        text = entry.get("text", "")
                    if text:
                        snippets.append(str(text))

                transcript = " ".join(snippets)
                item.metadata["transcript_chars"] = len(transcript)
                item.metadata["transcript"] = transcript[:12000]
            except Exception as exc:
                item.metadata["transcript_error"] = type(exc).__name__

        return items
