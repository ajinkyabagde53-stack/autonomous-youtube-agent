from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import ChannelConfig

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target

    with target.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_channel_config(path: str | Path = "config/channel.yaml") -> ChannelConfig:
    data = load_yaml(path)
    channel = data["channel"]

    return ChannelConfig(
        name=channel["name"],
        niche=channel["niche"],
        description=channel["description"],
        audience=data.get("audience", {}),
        goals=data.get("goals", {}),
        content=data.get("content", {}),
        monetization=data.get("monetization", {}),
        constraints=data.get("constraints", {}),
    )
