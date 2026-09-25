from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import ChannelConfig, Opportunity, ResearchItem


class OpportunityEngine:
    """Turn research signals into ranked, explainable opportunities."""

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    def generate(self, research: Iterable[ResearchItem]) -> list[Opportunity]:
        items = list(research)

        if not items:
            return self._seed_from_config()

        topic_counts = Counter(
            topic.strip().lower()
            for item in items
            for topic in item.topics
            if topic.strip()
        )

        opportunities: list[Opportunity] = []

        for topic, count in topic_counts.most_common(20):
            evidence = [
                f"{item.source}: {item.title}"
                for item in items
                if topic in {t.lower() for t in item.topics}
            ][:5]

            opportunities.append(
                Opportunity(
                    topic=topic,
                    angle=f"A practical, differentiated take on {topic}",
                    demand_signal=round(min(1.0, 0.35 + 0.12 * count), 2),
                    audience_fit=0.80 if self.config.niche.lower() in topic else 0.65,
                    competition_gap=0.50,
                    differentiation=0.70,
                    business_intent=0.55,
                    rationale=(
                        "The topic appears in collected research and can be "
                        "translated into a channel-fit angle."
                    ),
                    evidence=evidence,
                )
            )

        return sorted(opportunities, key=lambda item: item.score, reverse=True)

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
                    "pain point."
                ),
                evidence=["channel.yaml"],
            )
            for problem in self.config.audience.get("pain_points", [])
        ]
