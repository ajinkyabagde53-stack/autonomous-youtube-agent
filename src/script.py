from __future__ import annotations

import json

from .llm import NUMBER, STRING, STRING_LIST, LLMClient, LLMError, list_of, object_schema
from .models import ChannelConfig
from .prompting import production_context, target_minutes

SCRIPT_SCHEMA = object_schema({
    "title": STRING,
    "estimated_minutes": NUMBER,
    "hook": STRING,
    "sections": list_of(object_schema({
        "heading": STRING,
        "narration": STRING,
        "visual_direction": STRING,
    })),
    "transition_lines": STRING_LIST,
    "closing": STRING,
    "cta": STRING,
    "fact_check_queue": STRING_LIST,
})


class ScriptAgent:
    """Generate a structured script from an approved video brief."""

    def __init__(self, config: ChannelConfig, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient()

    def generate(
        self,
        brief: dict,
        territory: dict | None = None,
        intent: dict | None = None,
    ) -> dict:
        brief_for_prompt = {k: v for k, v in brief.items() if k != "fallback_reason"}
        prompt = f"""
Write a faceless YouTube script from this approved brief.

{production_context(self.config, territory, intent)}

Brief:
{json.dumps(brief_for_prompt, ensure_ascii=False)}

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
        try:
            return self.llm.complete_json(
                "You are an expert faceless YouTube scriptwriter.",
                prompt,
                SCRIPT_SCHEMA,
            )
        except LLMError as exc:
            return {
                "title": brief.get("working_title", ""),
                "estimated_minutes": target_minutes(self.config, intent) or 8,
                "hook": brief.get("opening_hook", ""),
                "sections": [],
                "transition_lines": [],
                "closing": "",
                "cta": brief.get("cta", ""),
                "fact_check_queue": brief.get("claims_to_verify", []),
                "fallback_reason": str(exc),
            }
