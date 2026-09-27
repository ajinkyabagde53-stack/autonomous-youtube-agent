from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelConfig:
    name: str
    niche: str
    description: str
    audience: dict[str, Any]
    goals: dict[str, Any]
    content: dict[str, Any]
    monetization: dict[str, Any]
    constraints: dict[str, Any]


@dataclass
class ResearchItem:
    source: str
    title: str
    url: str = ""
    summary: str = ""
    audience_problem: str = ""
    topics: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Opportunity:
    topic: str
    angle: str
    demand_signal: float
    audience_fit: float
    competition_gap: float
    differentiation: float
    business_intent: float
    rationale: str
    evidence: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        weights = {
            "demand_signal": 0.25,
            "audience_fit": 0.25,
            "competition_gap": 0.15,
            "differentiation": 0.20,
            "business_intent": 0.15,
        }
        return round(
            sum(getattr(self, key) * weight for key, weight in weights.items()),
            2,
        )


@dataclass
class ContentPlan:
    pillars: list[dict[str, Any]]
    series: list[dict[str, Any]]
    backlog: list[dict[str, Any]]


@dataclass
class ReferenceChannel:
    url: str
    channel_id: str = ""
    title: str = ""
    description: str = ""
    subscriber_count: int = 0
    video_count: int = 0
    view_count: int = 0
    country: str = ""
    published_at: str = ""
    uploads_playlist_id: str = ""
    topic_categories: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
