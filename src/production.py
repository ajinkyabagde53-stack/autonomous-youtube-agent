from __future__ import annotations

from typing import Any


class ProductionPlanner:
    """Convert a script into tool-agnostic production instructions."""

    def build(self, script: dict[str, Any]) -> dict[str, Any]:
        scenes = []

        for index, section in enumerate(script.get("sections", []), 1):
            scenes.append(
                {
                    "scene": index,
                    "narration": section.get("narration", ""),
                    "visual_direction": section.get("visual_direction", ""),
                    "asset_type": self._asset_type(section.get("visual_direction", "")),
                    "on_screen_text": section.get("heading", ""),
                }
            )

        return {
            "title": script.get("title", ""),
            "scenes": scenes,
            "voiceover": {
                "style": "natural, confident, conversational",
                "language": "English",
            },
            "editing_notes": [
                "Change visual treatment regularly enough to maintain attention.",
                "Use on-screen text only when it improves comprehension.",
                "Do not add visual claims that are unsupported by the narration.",
            ],
        }

    @staticmethod
    def _asset_type(direction: str) -> str:
        lowered = direction.lower()
        if any(word in lowered for word in ["chart", "graph", "data"]):
            return "data_visual"
        if any(word in lowered for word in ["screen", "website", "software"]):
            return "screen_recording"
        if any(word in lowered for word in ["diagram", "flow", "process"]):
            return "diagram"
        return "stock_or_generated_visual"
