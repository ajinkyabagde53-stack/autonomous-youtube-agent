from __future__ import annotations

import json

from .llm import LLMClient
from .models import ChannelConfig


class ScriptAgent:
    """Generate a structured script from an approved video brief."""

    def __init__(self, config: ChannelConfig, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient()

    def generate(self, brief: dict) -> dict:
        prompt = f"""
Write a faceless YouTube script from this approved brief.

Channel:
{self.config.description}

Audience:
{self.config.audience.get("primary", "")}

Brief:
{json.dumps(brief, ensure_ascii=False)}

Return JSON with:
- title
- estimated_minutes
- hook
- sections: array of objects with heading, narration, visual_direction
- transition_lines
- closing
- cta
- fact_check_queue

Rules:
- Do not invent facts, statistics, quotes, or sources.
- Mark unsupported claims for fact checking.
- Keep narration natural and spoken.
- Avoid generic filler.
- Each section should advance the viewer toward the promised outcome.
"""
        result = self.llm.complete_json(
            "You are an expert faceless YouTube scriptwriter.",
            prompt,
        )

        return result or {
            "title": brief.get("working_title", ""),
            "estimated_minutes": self.config.content.get("target_minutes", 8),
            "hook": brief.get("opening_hook", ""),
            "sections": [],
            "transition_lines": [],
            "closing": "",
            "cta": brief.get("cta", ""),
            "fact_check_queue": brief.get("claims_to_verify", []),
        }
