from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def write_json(filename: str, value: Any) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / filename
    target.write_text(
        json.dumps(_serialize(value), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def write_summary(channel_name: str, research_count: int, opportunities: list[Any], strategy: Any) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / "run_summary.md"
    top = sorted(opportunities, key=lambda x: x.score, reverse=True)[:5]

    lines = [
        "# Run Summary",
        "",
        f"**Channel:** {channel_name}",
        f"**Research items:** {research_count}",
        f"**Opportunities:** {len(opportunities)}",
        "",
        "## Top opportunities",
        "",
    ]

    if not top:
        lines.append("No opportunities were generated.")
    else:
        for index, item in enumerate(top, 1):
            lines.extend([
                f"### {index}. {item.topic}",
                f"- **Score:** {item.score}",
                f"- **Angle:** {item.angle}",
                f"- **Rationale:** {item.rationale}",
                "",
            ])

    lines.extend([
        "## Strategy",
        "",
        f"- Content pillars: {len(strategy.pillars)}",
        f"- Series: {len(strategy.series)}",
        f"- Backlog items: {len(strategy.backlog)}",
        "",
    ])

    target.write_text("\n".join(lines), encoding="utf-8")
    return target
