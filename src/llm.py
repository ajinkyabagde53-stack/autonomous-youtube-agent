from __future__ import annotations

import json
import os
from typing import Any

import anthropic


class LLMClient:
    """Small provider wrapper so agents do not depend directly on SDK details."""

    def __init__(self, model: str | None = None) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None

    def complete_json(self, system: str, prompt: str) -> dict[str, Any]:
        if not self.client:
            return {}

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        text = "\n".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        ).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
