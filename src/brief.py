from __future__ import annotations

import json

from .llm import LLMClient
from .models import ChannelConfig, Opportunity


class VideoBriefAgent:
    """Turn a selected opportunity into a production-ready creative brief."""

    def __init__(self, config: ChannelConfig, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient()

    def create(self, opportunity: Opportunity, intelligence: dict | None = None) -> dict:
        prompt = f"""
Create a YouTube video brief for this channel.

Channel:
{self.config.description}

Audience:
{self.config.audience.get("primary", "")}

Opportunity:
{json.dumps({
    "topic": opportunity.topic,
    "angle": opportunity.angle,
    "score": opportunity.score,
    "evidence": opportunity.evidence,
}, ensure_ascii=False)}

Supporting intelligence:
{json.dumps(intelligence or {}, ensure_ascii=False)}

Return JSON with:
- working_title
- alternative_titles
- viewer_promise
- opening_hook
- core_argument
- outline
- proof_points
- thumbnail_concept
- thumbnail_text
- cta
- claims_to_verify
- production_notes

Avoid unsupported claims. The goal is a useful, differentiated video rather than clickbait.
"""

        result = self.llm.complete_json(
            "You are a senior YouTube strategist creating evidence-aware video briefs.",
            prompt,
        )

        return result or {
            "working_title": opportunity.topic,
            "alternative_titles": [],
            "viewer_promise": opportunity.angle,
            "opening_hook": "",
            "core_argument": opportunity.angle,
            "outline": [],
            "proof_points": opportunity.evidence,
            "thumbnail_concept": "",
            "thumbnail_text": "",
            "cta": "",
            "claims_to_verify": [],
            "production_notes": [],
        }
