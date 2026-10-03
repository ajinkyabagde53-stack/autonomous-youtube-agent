from __future__ import annotations

import re
from typing import Any

from .llm import NUMBER, STRING, STRING_LIST, LLMClient, LLMError, object_schema

# Choices offered by the dashboard and CLI. "" means "let the prompt decide".
VIDEO_FORMATS = ("explainer", "tutorial", "documentary", "list", "commentary", "review", "short")
VIDEO_LENGTHS = {"short": 1, "5-8": 7, "8-15": 12, "15+": 20}  # target minutes
MAX_PROMPT_CHARS = 2000
MAX_QUERIES = 5

INTENT_SCHEMA = object_schema({
    "topic": STRING,
    "summary": STRING,
    "video_format": STRING,
    "target_minutes": NUMBER,
    "tone": STRING,
    "audience": STRING,
    "must_include": STRING_LIST,
    "avoid": STRING_LIST,
    "search_queries": STRING_LIST,
})


def _short_topic(prompt: str) -> str:
    """First sentence of the prompt, trimmed to a usable search phrase."""
    first = re.split(r"(?<=[.!?])\s+|\n", prompt.strip(), maxsplit=1)[0]
    return first[:120].strip(" .!?")


class IntentAgent:
    """Turn a creator's free-text request into a structured video intent.

    The intent says what the video is about and what kind of video it is.
    Research then looks for evidence about that topic on YouTube, so the
    creator decides the topic and the evidence decides the angle.
    """

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def parse(self, prompt: str, video_format: str = "", video_length: str = "") -> dict[str, Any]:
        prompt = prompt.strip()[:MAX_PROMPT_CHARS]
        video_format = video_format if video_format in VIDEO_FORMATS else ""
        video_length = video_length if video_length in VIDEO_LENGTHS else ""

        choices = []
        if video_format:
            choices.append(f"Format chosen by the creator: {video_format}")
        if video_length:
            choices.append(f"Length chosen by the creator: about {VIDEO_LENGTHS[video_length]} minutes")

        request = f"""
A YouTube creator described a video they want to make. Turn it into a brief.

CREATOR'S REQUEST:
{prompt}

{chr(10).join(choices)}

Return JSON with:
- topic: the subject in a few words, phrased the way viewers would search for it
- summary: one or two sentences on the video they want, in your own words
- video_format: the kind of video (explainer, tutorial, documentary, list,
  commentary, review, short, or another short label); "" if not stated
- target_minutes: the intended length in minutes; 0 if not stated
- tone: the requested tone or style; "" if not stated
- audience: who the video is for; "" if not stated
- must_include: points, examples or segments the creator asked for
- avoid: things the creator asked to avoid
- search_queries: 3 to 5 short YouTube search queries (2 to 6 words each)
  that would find existing videos on this topic. Cover the main topic, the
  way a beginner would phrase it, and one or two adjacent angles. Leave out
  style words such as "documentary" unless people search with them.

Do not invent requirements the creator did not state.
"""
        try:
            result = self.llm.complete_json(
                "You turn creators' video ideas into precise research briefs.",
                request,
                INTENT_SCHEMA,
            )
        except LLMError as exc:
            return self._fallback(prompt, video_format, video_length, str(exc))

        topic = str(result.get("topic", "")).strip() or _short_topic(prompt)
        queries = self._clean_queries(result.get("search_queries", []), topic)
        minutes = result.get("target_minutes") or 0
        return {
            "prompt": prompt,
            "topic": topic,
            "summary": str(result.get("summary", "")).strip(),
            "video_format": video_format or str(result.get("video_format", "")).strip(),
            "target_minutes": VIDEO_LENGTHS.get(video_length) or (
                float(minutes) if isinstance(minutes, (int, float)) and minutes > 0 else 0
            ),
            "tone": str(result.get("tone", "")).strip(),
            "audience": str(result.get("audience", "")).strip(),
            "must_include": self._clean_list(result.get("must_include", [])),
            "avoid": self._clean_list(result.get("avoid", [])),
            "search_queries": queries,
        }

    def _fallback(self, prompt: str, video_format: str, video_length: str, reason: str) -> dict[str, Any]:
        topic = _short_topic(prompt)
        return {
            "prompt": prompt,
            "topic": topic,
            "summary": prompt[:300],
            "video_format": video_format,
            "target_minutes": VIDEO_LENGTHS.get(video_length, 0),
            "tone": "",
            "audience": "",
            "must_include": [],
            "avoid": [],
            "search_queries": [topic] if topic else [],
            "error": reason,
        }

    @staticmethod
    def _clean_list(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        return [str(value).strip() for value in values if str(value).strip()][:8]

    @staticmethod
    def _clean_queries(values: Any, topic: str) -> list[str]:
        queries = IntentAgent._clean_list(values)
        if topic:
            queries.insert(0, topic)
        unique = list(dict.fromkeys(query.lower() for query in queries if query))
        return unique[:MAX_QUERIES]
