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
    """Turn research + intelligence into explainable opportunities.

    Scores are relative to the evidence collected in the current research set.
    They are prioritization signals, not predictions of future performance.
    """

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    def generate(
        self,
        research: Iterable[ResearchItem],
        intelligence: dict | None = None,
        territory: dict | None = None,
    ) -> list[Opportunity]:
        items = list(research)
        if not items:
            return self._seed_from_config()

        grouped: dict[str, list[ResearchItem]] = defaultdict(list)
        candidates = self._candidate_topics(items, intelligence)

        for candidate in candidates:
            candidate_tokens = _tokenize(candidate)
            matched = [
                item
                for item in items
                if candidate_tokens & _tokenize(item.title + " " + item.summary)
            ]
            grouped[candidate] = matched

        if not grouped:
            for item in items:
                for topic in item.topics:
                    topic = topic.strip().lower()
                    if topic:
                        grouped[topic].append(item)

        # Keep candidates even when there are zero direct matches: an empty
        # direct sample can itself be useful gap evidence.
        topic_stats: dict[str, dict[str, float]] = {}
        for topic, topic_items in grouped.items():
            views = [
                float(item.metadata.get("view_count", 0) or 0)
                for item in topic_items
            ]
            engagement = [self._engagement(item) for item in topic_items]
            topic_stats[topic] = {
                "count": len(topic_items),
                "views": (
                    math.log1p(sum(views) / max(1, len(views)))
                    if views
                    else 0.0
                ),
                "engagement": (
                    sum(engagement) / max(1, len(engagement))
                    if engagement
                    else 0.0
                ),
            }

        view_values = [stats["views"] for stats in topic_stats.values()]
        engagement_values = [stats["engagement"] for stats in topic_stats.values()]

        insights = intelligence.get("insights", {}) if intelligence else {}
        audience_evidence = (
            self._intelligence_terms(intelligence, "audience_pain_points")
            + self._intelligence_terms(intelligence, "desired_outcomes")
            + self._intelligence_terms(intelligence, "recurring_questions")
        )
        territory_audience = []
        if territory:
            territory_audience.append(str(territory.get("audience", "")))
            territory_audience.extend(
                str(value) for value in territory.get("sub_territories", [])
            )

        content_gaps = (
            self._intelligence_terms(intelligence, "content_gaps")
            + self._intelligence_terms(intelligence, "gap_candidates")
        )

        opportunities: list[Opportunity] = []

        for topic, stats in topic_stats.items():
            topic_tokens = _tokenize(topic)

            demand = (
                0.65
                * _normalized(
                    stats["views"],
                    min(view_values) if view_values else 0.0,
                    max(view_values) if view_values else 1.0,
                )
                + 0.35
                * _normalized(
                    stats["engagement"],
                    min(engagement_values) if engagement_values else 0.0,
                    max(engagement_values) if engagement_values else 1.0,
                )
            )

            # If this is an LLM-generated gap with no direct matching videos,
            # do not claim that it has no demand. Give it a neutral demand
            # signal and let the evidence notes explain the uncertainty.
            if not grouped[topic]:
                demand = 0.50

            audience_fit = self._keyword_overlap(
                topic_tokens,
                territory_audience + audience_evidence,
            )

            if not territory_audience and not audience_evidence:
                audience_fit = 0.55

            max_count = max((s["count"] for s in topic_stats.values()), default=1)
            saturation = stats["count"] / max(1, max_count)
            competition_gap = 1.0 - saturation

            gap_match = self._keyword_overlap(topic_tokens, content_gaps)
            differentiation = max(0.35, gap_match)

            business_intent = self._business_intent(
                topic,
                insights if isinstance(insights, dict) else {},
            )

            evidence = [
                f"{item.source}: {item.title}"
                for item in grouped[topic][:5]
            ]
            if not evidence:
                evidence.append(
                    "No direct reference-channel videos matched this candidate; "
                    "gap evidence requires wider validation."
                )

            rationale = (
                "Relative evidence score. Demand uses collected view and "
                "engagement signals when available; audience fit uses the "
                "observed reference-channel audience rather than the user's "
                "own channel configuration; competition gap reflects topic "
                "concentration in the collected sample; differentiation uses "
                "observed gap evidence; business intent is a topic-level "
                "commercial signal. These are not performance predictions."
            )

            opportunities.append(
                Opportunity(
                    topic=topic,
                    angle=f"A differentiated treatment of {topic}",
                    demand_signal=round(demand, 2),
                    audience_fit=round(audience_fit, 2),
                    competition_gap=round(competition_gap, 2),
                    differentiation=round(differentiation, 2),
                    business_intent=round(business_intent, 2),
                    rationale=rationale,
                    evidence=evidence,
                )
            )

        return sorted(opportunities, key=lambda item: item.score, reverse=True)

    @staticmethod
    def _candidate_topics(
        items: list[ResearchItem],
        intelligence: dict | None,
    ) -> list[str]:
        candidates = (
            OpportunityEngine._intelligence_terms(intelligence, "gap_candidates")
            + OpportunityEngine._intelligence_terms(intelligence, "content_gaps")
        )
        if candidates:
            return list(
                dict.fromkeys(
                    c.strip().lower() for c in candidates if c.strip()
                )
            )[:12]

        phrases = Counter()
        for item in items:
            tokens = [
                token
                for token in re.findall(r"[a-zA-Z0-9]+", item.title.lower())
                if len(token) > 3
            ]
            for size in (2, 3):
                for index in range(len(tokens) - size + 1):
                    phrase = " ".join(tokens[index:index + size])
                    phrases[phrase] += 1

        return [phrase for phrase, _ in phrases.most_common(12)]

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
        values = insights.get(key, []) if isinstance(insights, dict) else {}

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
    def _business_intent(topic: str, insights: dict) -> float:
        commercial_terms = {
            "how to", "best", "tool", "software", "course", "guide",
            "strategy", "automation", "review", "comparison", "template",
            "workflow", "career", "buy", "cost", "price", "investment",
            "insurance", "property", "finance", "consulting",
        }
        lowered = topic.lower()
        matches = sum(term in lowered for term in commercial_terms)

        # If the intelligence layer identifies desired outcomes or practical
        # questions, treat that as a separate signal from raw keyword matches.
        outcome_signal = 0.10 if insights.get("desired_outcomes") else 0.0
        return min(1.0, 0.45 + matches * 0.10 + outcome_signal)

    def _seed_from_config(self) -> list[Opportunity]:
        return [
            Opportunity(
                topic=problem,
                angle=f"Investigate the opportunity around {problem.lower()}.",
                demand_signal=0.45,
                audience_fit=0.75,
                competition_gap=0.50,
                differentiation=0.65,
                business_intent=0.45,
                rationale=(
                    "Starter hypothesis generated from the configured audience "
                    "only because no research evidence was available. It is not "
                    "presented as a discovered gap."
                ),
                evidence=["config/channel.yaml"],
            )
            for problem in self.config.audience.get("pain_points", [])
        ]
