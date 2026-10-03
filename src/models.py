from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
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


# Matched research items needed before an opportunity counts as fully evidenced.
EVIDENCE_TARGET = 3


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
    evidence_count: int = 0
    opportunity_id: str = ""
    history: dict[str, Any] = field(default_factory=dict)

    @property
    def tier(self) -> str:
        """Validated when research items back it, otherwise a hypothesis."""
        return "validated" if self.evidence_count > 0 else "hypothesis"

    @property
    def evidence_strength(self) -> float:
        return min(1.0, self.evidence_count / EVIDENCE_TARGET)

    @property
    def score(self) -> float:
        weights = {
            "demand_signal": 0.25,
            "audience_fit": 0.25,
            "competition_gap": 0.15,
            "differentiation": 0.20,
            "business_intent": 0.15,
        }
        signal = sum(getattr(self, key) * weight for key, weight in weights.items())
        # Thin evidence caps the score, so an unmatched idea cannot outrank
        # one that collected research actually supports.
        return round(signal * (0.6 + 0.4 * self.evidence_strength), 2)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["score"] = self.score
        data["tier"] = self.tier
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Opportunity":
        names = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in names})


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
