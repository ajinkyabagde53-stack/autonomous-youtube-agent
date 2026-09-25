from __future__ import annotations

import json

from .llm import LLMClient
from .models import ChannelConfig


class ThumbnailAgent:
    def __init__(self, config: ChannelConfig, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient()

    def generate(self, brief: dict) -> dict:
        prompt = f"""
Create three thumbnail concepts for this YouTube video brief:

{json.dumps(brief, ensure_ascii=False)}

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
        return self.llm.complete_json(
            "You are a YouTube thumbnail strategist for a faceless channel.",
            prompt,
        )
