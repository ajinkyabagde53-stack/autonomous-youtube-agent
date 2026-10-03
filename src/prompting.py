from __future__ import annotations

import json

from .intelligence import FALLBACK_TERRITORY_LABEL
from .models import ChannelConfig


def target_minutes(config: ChannelConfig, intent: dict | None = None) -> float | None:
    """The creator's requested length wins over the channel default."""
    requested = (intent or {}).get("target_minutes") or 0
    return requested if requested > 0 else config.content.get("target_minutes")


def production_context(
    config: ChannelConfig,
    territory: dict | None = None,
    intent: dict | None = None,
) -> str:
    """Prompt block that tells production agents what the video is about and for whom.

    Priority, highest first:
    1. The creator's prompt (intent): topic, format, tone, length, must-include
       and avoid lists.
    2. The researched territory: subject and observed audience.
    3. The channel config: voice and default format only.
    """
    territory = territory or {}
    intent = intent or {}
    label = territory.get("label", "")
    has_territory = bool(label) and label != FALLBACK_TERRITORY_LABEL

    constraints = config.constraints
    format_notes = {
        "faceless": constraints.get("faceless", False),
        "target_minutes": target_minutes(config, intent),
        "avoid_claims_without_evidence": constraints.get(
            "avoid_claims_without_evidence", True
        ),
    }

    blocks = []
    if intent:
        requested = {
            key: intent.get(key)
            for key in ("topic", "summary", "video_format", "tone", "audience", "must_include", "avoid")
            if intent.get(key)
        }
        blocks.append(
            "The creator's request (follow it; it overrides the channel's default "
            "format and tone):\n" + json.dumps(requested, ensure_ascii=False)
        )

    if has_territory:
        audience = intent.get("audience") or territory.get("audience") or "not evidenced in the research"
        blocks.append(
            f"Research territory (decides the subject):\n{label}\n"
            f"Sub-territories: {json.dumps(territory.get('sub_territories', []), ensure_ascii=False)}\n\n"
            f"Audience (who the video is for):\n{audience}"
        )
        blocks.append(
            "Your channel (use for voice and format only; it must not change the "
            f"subject or audience):\n{config.name}: {config.description}\n"
            f"Format: {json.dumps(format_notes)}"
        )
    elif intent:
        blocks.append(
            f"Your channel (use for voice only):\n{config.name}: {config.description}\n"
            f"Format: {json.dumps(format_notes)}"
        )
    else:
        blocks.append(
            "No research territory was inferred, so use the channel configuration.\n\n"
            f"Channel:\n{config.name}: {config.description}\n\n"
            f"Audience:\n{config.audience.get('primary', '')}\n\n"
            f"Format: {json.dumps(format_notes)}"
        )

    return "\n\n".join(blocks)
