from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .analytics import VideoPerformance
from .models import Opportunity


@dataclass
class PerformanceMemory:
    """Persistent channel-learning representation.

    Values are descriptive signals from the channel's own history. They are
    not forecasts and should not be treated as guarantees of future results.
    """

    topic_signals: dict[str, dict[str, float]] = field(default_factory=dict)
    format_signals: dict[str, dict[str, float]] = field(default_factory=dict)
    title_signals: dict[str, dict[str, float]] = field(default_factory=dict)


class LearningAgent:
    """Turn observed channel performance into reusable content signals."""

    def build_memory(
        self,
        videos: list[VideoPerformance],
        opportunity_by_video: dict[str, Opportunity] | None = None,
    ) -> PerformanceMemory:
        opportunity_by_video = opportunity_by_video or {}
        topic_values: dict[str, list[float]] = defaultdict(list)
        title_values: dict[str, list[float]] = defaultdict(list)

        for video in videos:
            if video.ctr is not None:
                title_values[self._title_pattern(video.title)].append(video.ctr)

            opportunity = opportunity_by_video.get(video.video_id)
            if opportunity and video.average_percentage_viewed is not None:
                topic_values[opportunity.topic].append(
                    video.average_percentage_viewed
                )

        return PerformanceMemory(
            topic_signals={
                topic: self._aggregate(values)
                for topic, values in topic_values.items()
            },
            title_signals={
                pattern: self._aggregate(values)
                for pattern, values in title_values.items()
            },
        )

    def apply_to_opportunities(
        self,
        opportunities: list[Opportunity],
        memory: PerformanceMemory,
    ) -> list[Opportunity]:
        """Add historical channel evidence to opportunity rationale.

        The existing score remains the same. Historical evidence is surfaced
        separately to avoid hiding how an opportunity was originally scored.
        """

        adjusted: list[Opportunity] = []

        for opportunity in opportunities:
            history = memory.topic_signals.get(opportunity.topic)
            if history:
                evidence = [
                    *opportunity.evidence,
                    (
                        f"Channel history: average observed retention "
                        f"{history['mean']:.2f} across {int(history['count'])} video(s) "
                        f"mapped to this topic."
                    ),
                ]
                opportunity = Opportunity(
                    topic=opportunity.topic,
                    angle=opportunity.angle,
                    demand_signal=opportunity.demand_signal,
                    audience_fit=opportunity.audience_fit,
                    competition_gap=opportunity.competition_gap,
                    differentiation=opportunity.differentiation,
                    business_intent=opportunity.business_intent,
                    rationale=opportunity.rationale + " Historical channel evidence is attached separately.",
                    evidence=evidence,
                )

            adjusted.append(opportunity)

        return adjusted

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
        if "why" in lowered:
            return "why"
        if "best" in lowered:
            return "best"
        if " vs " in lowered:
            return "comparison"
        if any(char.isdigit() for char in title):
            return "number-led"
        return "general"
