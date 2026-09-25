from __future__ import annotations

from typing import Iterable

from .models import ChannelConfig, ContentPlan, Opportunity


class StrategyAgent:
    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    def build(self, opportunities: Iterable[Opportunity]) -> ContentPlan:
        ranked = list(opportunities)
        configured_pillars = self.config.content.get("pillars", [])

        pillars = [
            {
                "name": pillar,
                "role": "Core content pillar",
                "topics": [
                    item.topic
                    for item in ranked
                    if pillar.lower() in item.topic.lower()
                ][:5],
            }
            for pillar in configured_pillars
        ]

        series = [
            {
                "name": f"{pillar} — Explained",
                "format": "repeatable long-form series",
                "purpose": "Build topical authority and create a recognizable format.",
            }
            for pillar in configured_pillars
        ]

        backlog = [
            {
                "priority": index + 1,
                "topic": item.topic,
                "angle": item.angle,
                "score": item.score,
                "evidence": item.evidence,
            }
            for index, item in enumerate(ranked[:20])
        ]

        return ContentPlan(pillars=pillars, series=series, backlog=backlog)
