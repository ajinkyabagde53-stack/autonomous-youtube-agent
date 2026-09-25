from __future__ import annotations

import json

from .llm import LLMClient
from .models import ChannelConfig, ResearchItem


class IntelligenceAgent:
    """Convert raw research into structured audience and content intelligence."""

    def __init__(self, config: ChannelConfig, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient()

    def analyze(self, items: list[ResearchItem]) -> dict:
        compact = [
            {
                "source": item.source,
                "title": item.title,
                "summary": item.summary[:1000],
                "topics": item.topics,
                "hooks": item.hooks,
                "metadata": {
                    k: v for k, v in item.metadata.items()
                    if k != "transcript"
                },
            }
            for item in items[:40]
        ]

        if not compact:
            return {"items_analyzed": 0, "insights": {}}

        prompt = f"""
Channel niche: {self.config.niche}
Primary audience: {self.config.audience.get("primary", "")}

Analyze the research below. Return JSON with:
- recurring_questions
- audience_pain_points
- desired_outcomes
- topic_patterns
- hook_patterns
- title_patterns
- content_gaps
- evidence_notes

Each should be an array. Do not invent metrics or facts. If evidence is weak, say so.

RESEARCH:
{json.dumps(compact, ensure_ascii=False)}
"""

        result = self.llm.complete_json(
            "You are an evidence-first YouTube audience and content intelligence analyst.",
            prompt,
        )

        return {"items_analyzed": len(items), "insights": result}
