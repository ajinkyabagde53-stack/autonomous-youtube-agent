from __future__ import annotations

from typing import Iterable

from .intelligence import FALLBACK_TERRITORY_LABEL
from .models import ChannelConfig, ContentPlan, Opportunity
from .text import coverage, tokenize


class StrategyAgent:
    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    def build(
        self,
        opportunities: Iterable[Opportunity],
        territory: dict | None = None,
    ) -> ContentPlan:
        ranked = list(opportunities)
        pillar_names, source = self._pillar_names(territory)

        # Assign each opportunity to the pillar sharing the most words with it.
        assigned: dict[str, list[str]] = {name: [] for name in pillar_names}
        for item in ranked:
            topic_tokens = tokenize(item.topic + " " + item.angle)
            best_name, best_score = None, 0.0
            for name in pillar_names:
                score = coverage(tokenize(name), topic_tokens)
                if score > best_score:
                    best_name, best_score = name, score
            if best_name and len(assigned[best_name]) < 5:
                assigned[best_name].append(item.topic)

        pillars = [
            {
                "name": name,
                "role": "Core content pillar",
                "source": source,
                "topics": assigned[name],
            }
            for name in pillar_names
        ]

        series = [
            {
                "name": f"{name} — Explained",
                "format": "repeatable long-form series",
                "purpose": "Build topical authority and create a recognizable format.",
            }
            for name in pillar_names
        ]

        backlog = [
            {
                "priority": index + 1,
                "opportunity_id": item.opportunity_id,
                "topic": item.topic,
                "angle": item.angle,
                "score": item.score,
                "tier": item.tier,
                "evidence": item.evidence,
            }
            for index, item in enumerate(ranked[:20])
        ]

        return ContentPlan(pillars=pillars, series=series, backlog=backlog)

    def _pillar_names(self, territory: dict | None) -> tuple[list[str], str]:
        """Pillars follow the researched territory; config pillars are the fallback."""
        territory = territory or {}
        label = territory.get("label", "")
        subs = [str(value) for value in territory.get("sub_territories", []) if str(value).strip()]
        if subs and label and label != FALLBACK_TERRITORY_LABEL:
            return subs, "research territory"
        return list(self.config.content.get("pillars", [])), "channel config"
