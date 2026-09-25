from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Iterable

from .models import ChannelConfig, Opportunity, ResearchItem


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", value.lower())
        if len(token) > 2
    }


def _normalized(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.5
    return max(0.0, min(1.0, (value - low) / (high - low)))


class OpportunityEngine:
    """Turn research + intelligence into explainable content opportunities.

    Scores are relative to the evidence collected in the current research set.
    They are prioritization signals, not predictions of future video performance.
    """

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    def generate(
        self,
        research: Iterable[ResearchItem],
        intelligence: dict | None = None,
    ) -> list[Opportunity]:
        items = list(research)
        if not items:
            return self._seed_from_config()

        grouped: dict[str, list[ResearchItem]] = defaultdict(list)
        for item in items:
            for topic in item.topics:
                topic = topic.strip().lower()
                if topic:
                    grouped[topic].append(item)

        topic_stats: dict[str, dict[str, float]] = {}
        for topic, topic_items in grouped.items():
            views = [
                float(item.metadata.get("view_count", 0) or 0)
                for item in topic_items
            ]
            engagement = [
                self._engagement(item)
                for item in topic_items
            ]
            topic_stats[topic] = {
                "count": len(topic_items),
                "views": math.log1p(sum(views) / max(1, len(views))),
                "engagement": sum(engagement) / max(1, len(engagement)),
            }

        view_values = [stats["views"] for stats in topic_stats.values()]
        engagement_values = [stats["engagement"] for stats in topic_stats.values()]
        max_count = max(stats["count"] for stats in topic_stats.values())

        content_gaps = self._intelligence_terms(
            intelligence,
            "content_gaps",
        )
        audience_problems = self._intelligence_terms(
            intelligence,
            "audience_pain_points",
        )

        opportunities: list[Opportunity] = []

        for topic, stats in topic_stats.items():
            topic_tokens = _tokenize(topic)

            demand = (
                0.65 * _normalized(stats["views"], min(view_values), max(view_values))
                + 0.35 * _normalized(
                    stats["engagement"],
                    min(engagement_values),
                    max(engagement_values),
                )
            )

            audience_fit = self._keyword_overlap(
                topic_tokens,
                [
                    self.config.audience.get("primary", ""),
                    *self.config.audience.get("pain_points", []),
                    *audience_problems,
                ],
            )

            saturation = stats["count"] / max(1, max_count)
            competition_gap = 1.0 - saturation

            gap_match = self._keyword_overlap(topic_tokens, content_gaps)
            differentiation = max(0.35, gap_match)

            business_intent = self._business_intent(topic)

            evidence = [
                f"{item.source}: {item.title}"
                for item in grouped[topic][:5]
            ]

            rationale = (
                "Demand uses relative view and engagement signals from the "
                "collected sample; competition gap reflects how concentrated "
                "the topic is in that sample; audience fit and differentiation "
                "use configured audience evidence and optional LLM intelligence."
            )

            opportunities.append(
                Opportunity(
                    topic=topic,
                    angle=f"A practical, differentiated take on {topic}",
                    demand_signal=round(demand, 2),
                    audience_fit=round(audience_fit, 2),
                    competition_gap=round(competition_gap, 2),
                    differentiation=round(differentiation, 2),
                    business_intent=round(business_intent, 2),
                    rationale=rationale,
                    evidence=evidence,
                )
            )

        return sorted(
            opportunities,
            key=lambda item: item.score,
            reverse=True,
        )

    @staticmethod
    def _engagement(item: ResearchItem) -> float:
        views = float(item.metadata.get("view_count", 0) or 0)
        likes = float(item.metadata.get("like_count", 0) or 0)
        comments = float(item.metadata.get("comment_count", 0) or 0)

        if views <= 0:
            return 0.0

        return min(1.0, ((likes + comments * 4) / views) * 100)

    @staticmethod
    def _intelligence_terms(
        intelligence: dict | None,
        key: str,
    ) -> list[str]:
        if not intelligence:
            return []

        insights = intelligence.get("insights", intelligence)
        values = insights.get(key, []) if isinstance(insights, dict) else []

        if isinstance(values, list):
            return [str(value) for value in values]
        return []

    @staticmethod
    def _keyword_overlap(topic_tokens: set[str], candidates: list[str]) -> float:
        if not topic_tokens or not candidates:
            return 0.55

        candidate_tokens = set()
        for candidate in candidates:
            candidate_tokens |= _tokenize(candidate)

        overlap = len(topic_tokens & candidate_tokens)
        return max(0.35, min(1.0, overlap / max(1, len(topic_tokens))))

    @staticmethod
    def _business_intent(topic: str) -> float:
        commercial_terms = {
            "how to", "best", "tool", "software", "course", "guide",
            "strategy", "automation", "review", "comparison", "template",
            "workflow", "career", "buy",
        }
        lowered = topic.lower()
        matches = sum(term in lowered for term in commercial_terms)
        return min(1.0, 0.45 + matches * 0.10)

    def _seed_from_config(self) -> list[Opportunity]:
        return [
            Opportunity(
                topic=problem,
                angle=f"Solve: {problem}",
                demand_signal=0.45,
                audience_fit=0.75,
                competition_gap=0.50,
                differentiation=0.65,
                business_intent=0.45,
                rationale=(
                    "Seed opportunity generated from a configured audience "
                    "pain point. It should be replaced by live research."
                ),
                evidence=["config/channel.yaml"],
            )
            for problem in self.config.audience.get("pain_points", [])
        ]
