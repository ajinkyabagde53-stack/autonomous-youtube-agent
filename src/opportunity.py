from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from .models import ChannelConfig, Opportunity, ResearchItem
from .text import coverage, matches, title_tokens, tokenize

MAX_CANDIDATES = 12


def _normalized(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.5
    return max(0.0, min(1.0, (value - low) / (high - low)))


def opportunity_id(topic: str, territory_label: str = "") -> str:
    """Stable ID so a published video can be traced back to its opportunity."""
    key = f"{territory_label.strip().lower()}|{topic.strip().lower()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


@dataclass
class Candidate:
    topic: str
    angle: str = ""
    supporting_ids: list[int] = field(default_factory=list)
    note: str = ""


class OpportunityEngine:
    """Turn research + intelligence into explainable opportunities.

    Scores are relative to the evidence collected in the current research set.
    They are prioritization signals, not predictions of future performance.
    Candidates with no supporting research are kept as hypotheses: they are
    ranked after validated opportunities and their score is capped.
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

        territory = territory or {}
        candidates = self._candidates(items, intelligence)
        item_tokens = [tokenize(item.title + " " + item.summary) for item in items]
        support = {
            candidate.topic: self._supporting_items(candidate, items, item_tokens)
            for candidate in candidates
        }

        topic_stats: dict[str, dict[str, float]] = {}
        for topic, topic_items in support.items():
            if not topic_items:
                continue
            views = [float(item.metadata.get("view_count", 0) or 0) for item in topic_items]
            engagement = [self._engagement(item) for item in topic_items]
            topic_stats[topic] = {
                "count": len(topic_items),
                "views": math.log1p(sum(views) / len(views)),
                "engagement": sum(engagement) / len(engagement),
            }

        # Normalize against supported topics only, so unsupported hypotheses
        # do not stretch the range.
        view_values = [stats["views"] for stats in topic_stats.values()] or [0.0]
        engagement_values = [stats["engagement"] for stats in topic_stats.values()] or [0.0]
        max_count = max((stats["count"] for stats in topic_stats.values()), default=1)

        insights = self._insights(intelligence)
        audience_evidence = (
            self._intelligence_terms(intelligence, "audience_pain_points")
            + self._intelligence_terms(intelligence, "desired_outcomes")
            + self._intelligence_terms(intelligence, "recurring_questions")
        )
        territory_audience = []
        if territory:
            territory_audience.append(str(territory.get("audience", "")))
            territory_audience.extend(str(value) for value in territory.get("sub_territories", []))

        gap_terms = (
            self._intelligence_terms(intelligence, "content_gaps")
            + self._intelligence_terms(intelligence, "gap_candidates")
        )

        opportunities: list[Opportunity] = []
        for candidate in candidates:
            topic = candidate.topic
            topic_tokens = tokenize(topic)
            matched = support[topic]

            if matched:
                stats = topic_stats[topic]
                demand = (
                    0.65 * _normalized(stats["views"], min(view_values), max(view_values))
                    + 0.35 * _normalized(stats["engagement"], min(engagement_values), max(engagement_values))
                )
                competition_gap = 1.0 - stats["count"] / max(1, max_count)
            else:
                # Unknown, not "high demand, no competition".
                demand = 0.5
                competition_gap = 0.5

            if territory_audience or audience_evidence:
                audience_fit = self._keyword_overlap(topic_tokens, territory_audience + audience_evidence)
            else:
                audience_fit = 0.55

            differentiation = max(0.35, self._keyword_overlap(topic_tokens, gap_terms))
            business_intent = self._business_intent(topic, insights)

            evidence = [f"{item.source}: {item.title}" for item in matched[:5]]
            if candidate.note:
                evidence.append(f"Analyst note: {candidate.note}")
            if not matched:
                evidence.append(
                    "No collected video directly supports this candidate; treat it "
                    "as a hypothesis that needs validation."
                )

            opportunities.append(
                Opportunity(
                    topic=topic,
                    angle=candidate.angle,
                    demand_signal=round(demand, 2),
                    audience_fit=round(audience_fit, 2),
                    competition_gap=round(competition_gap, 2),
                    differentiation=round(differentiation, 2),
                    business_intent=round(business_intent, 2),
                    rationale=(
                        "Relative evidence score. Demand uses view and engagement "
                        "signals of the matching videos; audience fit uses the "
                        "observed reference-channel audience; competition gap "
                        "reflects how concentrated the topic is in the sample; "
                        "differentiation uses observed gap evidence; business "
                        "intent is a topic-level commercial signal. Scores are "
                        "capped when fewer than three videos support the topic. "
                        "These are not performance predictions."
                    ),
                    evidence=evidence,
                    evidence_count=len(matched),
                    opportunity_id=opportunity_id(topic, str(territory.get("label", ""))),
                )
            )

        return sorted(
            opportunities,
            key=lambda item: (item.tier == "validated", item.score),
            reverse=True,
        )

    def _candidates(self, items: list[ResearchItem], intelligence: dict | None) -> list[Candidate]:
        insights = self._insights(intelligence)
        raw_candidates = insights.get("gap_candidates", [])
        candidates = [
            candidate
            for candidate in (self._parse_candidate(raw) for raw in raw_candidates)
            if candidate
        ] if isinstance(raw_candidates, list) else []

        if not candidates:
            candidates = [
                Candidate(topic=gap)
                for gap in self._intelligence_terms(intelligence, "content_gaps")
            ]

        if not candidates:
            candidates = [Candidate(topic=phrase) for phrase in self._title_phrases(items)]

        unique: dict[str, Candidate] = {}
        for candidate in candidates:
            key = candidate.topic.strip().lower()
            if key and key not in unique:
                unique[key] = candidate
        return list(unique.values())[:MAX_CANDIDATES]

    @staticmethod
    def _parse_candidate(raw: Any) -> Candidate | None:
        if isinstance(raw, str):
            return Candidate(topic=raw.strip()) if raw.strip() else None
        if not isinstance(raw, dict):
            return None
        topic = str(raw.get("topic") or raw.get("title") or "").strip()
        if not topic:
            return None
        ids = []
        for value in raw.get("supporting_item_ids", []) or []:
            try:
                ids.append(int(value))
            except (TypeError, ValueError):
                continue
        return Candidate(
            topic=topic,
            angle=str(raw.get("angle", "")).strip(),
            supporting_ids=ids,
            note=str(raw.get("evidence", "")).strip(),
        )

    @staticmethod
    def _title_phrases(items: list[ResearchItem]) -> list[str]:
        phrases: Counter[str] = Counter()
        for item in items:
            tokens = title_tokens(item.title)
            for size in (2, 3):
                for index in range(len(tokens) - size + 1):
                    phrases[" ".join(tokens[index:index + size])] += 1
        return [phrase for phrase, _ in phrases.most_common(MAX_CANDIDATES)]

    @staticmethod
    def _supporting_items(
        candidate: Candidate,
        items: list[ResearchItem],
        item_tokens: list[set[str]],
    ) -> list[ResearchItem]:
        """Items the analyst cited, plus items that cover most of the topic's words."""
        chosen: dict[int, ResearchItem] = {}
        for index in candidate.supporting_ids:
            if 0 <= index < len(items):
                chosen[index] = items[index]

        topic_tokens = tokenize(candidate.topic)
        for index, tokens in enumerate(item_tokens):
            if index not in chosen and matches(topic_tokens, tokens):
                chosen[index] = items[index]
        return list(chosen.values())

    @staticmethod
    def _engagement(item: ResearchItem) -> float:
        views = float(item.metadata.get("view_count", 0) or 0)
        likes = float(item.metadata.get("like_count", 0) or 0)
        comments = float(item.metadata.get("comment_count", 0) or 0)

        if views <= 0:
            return 0.0

        return min(1.0, ((likes + comments * 4) / views) * 100)

    @staticmethod
    def _insights(intelligence: dict | None) -> dict:
        if not isinstance(intelligence, dict):
            return {}
        insights = intelligence.get("insights", intelligence)
        return insights if isinstance(insights, dict) else {}

    @staticmethod
    def _intelligence_terms(intelligence: dict | None, key: str) -> list[str]:
        values = OpportunityEngine._insights(intelligence).get(key, [])
        if not isinstance(values, list):
            return []

        terms = []
        for value in values:
            if isinstance(value, dict):
                value = value.get("topic") or value.get("title") or ""
            if isinstance(value, str) and value.strip():
                terms.append(value.strip())
        return terms

    @staticmethod
    def _keyword_overlap(topic_tokens: set[str], candidates: list[str]) -> float:
        if not topic_tokens or not candidates:
            return 0.55

        candidate_tokens: set[str] = set()
        for candidate in candidates:
            candidate_tokens |= tokenize(candidate)

        return max(0.35, min(1.0, coverage(topic_tokens, candidate_tokens)))

    @staticmethod
    def _business_intent(topic: str, insights: dict) -> float:
        commercial_terms = {
            "how to", "best", "tool", "software", "course", "guide",
            "strategy", "automation", "review", "comparison", "template",
            "workflow", "career", "buy", "cost", "price", "investment",
            "insurance", "property", "finance", "consulting",
        }
        lowered = topic.lower()
        matches_found = sum(term in lowered for term in commercial_terms)

        # If the intelligence layer identifies desired outcomes or practical
        # questions, treat that as a separate signal from raw keyword matches.
        outcome_signal = 0.10 if insights.get("desired_outcomes") else 0.0
        return min(1.0, 0.45 + matches_found * 0.10 + outcome_signal)

    def _seed_from_config(self) -> list[Opportunity]:
        """Starter hypotheses from config/channel.yaml when no research exists.

        They carry no research evidence, so they are always the "hypothesis"
        tier and say so in their rationale.
        """
        return [
            Opportunity(
                topic=problem,
                angle="",
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
                opportunity_id=opportunity_id(problem),
            )
            for problem in self.config.audience.get("pain_points", [])
        ]
