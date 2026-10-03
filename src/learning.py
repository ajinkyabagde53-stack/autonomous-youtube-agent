from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Any

from .analytics import VideoPerformance
from .models import Opportunity
from .text import coverage, tokenize

# How closely a new opportunity's topic must match a remembered topic.
TOPIC_MATCH_THRESHOLD = 0.6


@dataclass
class PerformanceMemory:
    """Persistent channel-learning representation.

    Values are descriptive signals from the channel's own history. They are
    not forecasts and should not be treated as guarantees of future results.

    - topic_signals: retention (% viewed) per opportunity topic, for videos
      recorded with `main.py --record-published`.
    - title_signals: thumbnail CTR per title pattern when CTR data was
      imported, otherwise views per title pattern (see `title_metric`).
    - format_signals: retention per video-length bucket.
    """

    topic_signals: dict[str, dict[str, float]] = field(default_factory=dict)
    format_signals: dict[str, dict[str, float]] = field(default_factory=dict)
    title_signals: dict[str, dict[str, float]] = field(default_factory=dict)
    title_metric: str = ""
    videos_analyzed: int = 0
    updated_at: str = ""
    notes: list[str] = field(default_factory=list)


def duration_bucket(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    if seconds <= 60:
        return "short (60s or less)"
    if seconds < 8 * 60:
        return "1-8 min"
    if seconds <= 20 * 60:
        return "8-20 min"
    return "over 20 min"


class LearningAgent:
    """Turn observed channel performance into reusable content signals."""

    def build_memory(
        self,
        videos: list[VideoPerformance],
        opportunity_by_video: dict[str, Any] | None = None,
        updated_at: str = "",
    ) -> PerformanceMemory:
        """Aggregate performance into memory.

        `opportunity_by_video` maps a video ID to the opportunity it was made
        from: an Opportunity, or just its topic string (as stored by the
        published-video registry).
        """
        opportunity_by_video = opportunity_by_video or {}
        topic_values: dict[str, list[float]] = defaultdict(list)
        format_values: dict[str, list[float]] = defaultdict(list)
        ctr_by_pattern: dict[str, list[float]] = defaultdict(list)
        views_by_pattern: dict[str, list[float]] = defaultdict(list)

        for video in videos:
            pattern = self._title_pattern(video.title) if video.title else None
            if pattern and video.ctr is not None:
                ctr_by_pattern[pattern].append(video.ctr)
            if pattern and video.views is not None:
                views_by_pattern[pattern].append(float(video.views))

            bucket = duration_bucket(video.duration_seconds)
            if bucket and video.average_percentage_viewed is not None:
                format_values[bucket].append(video.average_percentage_viewed)

            source = opportunity_by_video.get(video.video_id)
            topic = getattr(source, "topic", source)
            if topic and video.average_percentage_viewed is not None:
                topic_values[str(topic)].append(video.average_percentage_viewed)

        notes = []
        untitled = sum(1 for video in videos if not video.title)
        if untitled:
            notes.append(f"{untitled} video(s) had no title, so they are left out of title signals.")
        if ctr_by_pattern:
            title_metric, title_values = "ctr", ctr_by_pattern
        else:
            title_metric, title_values = "views", views_by_pattern
            if videos:
                notes.append(
                    "No thumbnail CTR was imported (use --ctr-csv), so title "
                    "signals compare views instead."
                )
        if videos and not topic_values:
            notes.append(
                "No analysed video is linked to an opportunity yet; record "
                "published videos with --record-published to learn per topic."
            )

        return PerformanceMemory(
            topic_signals={topic: self._aggregate(v) for topic, v in topic_values.items()},
            format_signals={bucket: self._aggregate(v) for bucket, v in format_values.items()},
            title_signals={pattern: self._aggregate(v) for pattern, v in title_values.items()},
            title_metric=title_metric if title_values else "",
            videos_analyzed=len(videos),
            updated_at=updated_at,
            notes=notes,
        )

    def apply_to_opportunities(
        self,
        opportunities: list[Opportunity],
        memory: PerformanceMemory,
    ) -> list[Opportunity]:
        """Attach the channel's own history to matching opportunities.

        Scores are left unchanged. History is surfaced separately, as evidence
        and in `Opportunity.history`, so it never hides how a score was made.
        """
        adjusted: list[Opportunity] = []
        for opportunity in opportunities:
            match = self._matching_topic(opportunity.topic, memory)
            if not match:
                adjusted.append(opportunity)
                continue

            topic, history = match
            note = (
                f"Channel history: {int(history['count'])} of your video(s) on "
                f"'{topic}' averaged {history['mean']:.1f}% viewed "
                f"(range {history['min']:.1f}-{history['max']:.1f}%)."
            )
            adjusted.append(replace(
                opportunity,
                evidence=[*opportunity.evidence, note],
                history={"matched_topic": topic, "retention": history},
            ))
        return adjusted

    @staticmethod
    def _matching_topic(
        topic: str,
        memory: PerformanceMemory,
    ) -> tuple[str, dict[str, float]] | None:
        if topic in memory.topic_signals:
            return topic, memory.topic_signals[topic]

        tokens = tokenize(topic)
        best: tuple[str, dict[str, float]] | None = None
        best_score = 0.0
        for known, history in memory.topic_signals.items():
            known_tokens = tokenize(known)
            # Require the match in both directions so a broad topic does not
            # absorb every narrower one.
            score = min(coverage(tokens, known_tokens), coverage(known_tokens, tokens))
            if score >= TOPIC_MATCH_THRESHOLD and score > best_score:
                best, best_score = (known, history), score
        return best

    @staticmethod
    def _aggregate(values: list[float]) -> dict[str, float]:
        if not values:
            return {"mean": 0.0, "min": 0.0, "max": 0.0, "count": 0.0}

        return {
            "mean": round(sum(values) / len(values), 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "count": float(len(values)),
        }

    @staticmethod
    def _title_pattern(title: str) -> str:
        lowered = title.lower()
        if "how to" in lowered:
            return "how-to"
        if lowered.startswith("why") or " why " in f" {lowered} ":
            return "why"
        if "best" in lowered:
            return "best"
        if " vs " in lowered or " vs. " in lowered or " versus " in lowered:
            return "comparison"
        if "?" in title:
            return "question"
        if any(char.isdigit() for char in title):
            return "number-led"
        return "general"
