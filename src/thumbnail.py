from __future__ import annotations

import json

from .llm import STRING, LLMClient, LLMError, list_of, object_schema
from .models import ChannelConfig

THUMBNAIL_SCHEMA = object_schema({
    "concepts": list_of(object_schema({
        "concept_name": STRING,
        "composition": STRING,
        "focal_element": STRING,
        "text": STRING,
        "emotional_tension": STRING,
        "generation_prompt": STRING,
    })),
    "selection_notes": STRING,
})


class ThumbnailAgent:
    def __init__(self, config: ChannelConfig, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient()

    def generate(self, brief: dict) -> dict:
        brief_for_prompt = {k: v for k, v in brief.items() if k != "fallback_reason"}
        prompt = f"""
Create three thumbnail concepts for this YouTube video brief:

{json.dumps(brief_for_prompt, ensure_ascii=False)}

Return JSON with:
- concepts: array of 3 objects
  - concept_name
  - composition
  - focal_element
  - text
  - emotional_tension
  - generation_prompt
- selection_notes

Keep thumbnail text short. Do not promise something the video cannot deliver.
"""
        try:
            return self.llm.complete_json(
                "You are a YouTube thumbnail strategist for a faceless channel.",
                prompt,
                THUMBNAIL_SCHEMA,
            )
        except LLMError as exc:
            return {
                "concepts": [],
                "selection_notes": "",
                "fallback_reason": str(exc),
            }
