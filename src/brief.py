from __future__ import annotations

import json

from .llm import STRING, STRING_LIST, LLMClient, LLMError, object_schema
from .models import ChannelConfig, Opportunity
from .prompting import production_context

BRIEF_SCHEMA = object_schema({
    "working_title": STRING,
    "alternative_titles": STRING_LIST,
    "viewer_promise": STRING,
    "opening_hook": STRING,
    "core_argument": STRING,
    "outline": STRING_LIST,
    "proof_points": STRING_LIST,
    "thumbnail_concept": STRING,
    "thumbnail_text": STRING,
    "cta": STRING,
    "claims_to_verify": STRING_LIST,
    "production_notes": STRING_LIST,
})


class VideoBriefAgent:
    """Turn a selected opportunity into a production-ready creative brief."""

    def __init__(self, config: ChannelConfig, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient()

    def create(
        self,
        opportunity: Opportunity,
        intelligence: dict | None = None,
        territory: dict | None = None,
        intent: dict | None = None,
    ) -> dict:
        prompt = f"""
Create a YouTube video brief.

{production_context(self.config, territory, intent)}

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

        try:
            return self.llm.complete_json(
                "You are a senior YouTube strategist creating evidence-aware video briefs.",
                prompt,
                BRIEF_SCHEMA,
            )
        except LLMError as exc:
            return {
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
                "fallback_reason": str(exc),
            }
