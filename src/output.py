from __future__ import annotations

import json
import shutil
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
# Per-run artifacts: outputs/runs/<run id>/, with the last completed run
# copied to outputs/latest/.
OUTPUT_DIR = ROOT / "outputs"
# State that outlives a run: channel memory, published-video registry, analytics.
DATA_DIR = ROOT / "data"

RUN_FILE = "run.json"


def _serialize(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        if hasattr(value, "to_dict"):
            return _serialize(value.to_dict())
        return _serialize(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def dump_json(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_serialize(value), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def data_path(filename: str) -> Path:
    # Read DATA_DIR at call time so tests can point it at a temp folder.
    return DATA_DIR / filename


def write_data_json(filename: str, value: Any) -> Path:
    return dump_json(data_path(filename), value)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunWriter:
    """Writes one run's artifacts to outputs/runs/<run id>/."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    @property
    def run_id(self) -> str:
        return self.run_dir.name

    @classmethod
    def create(cls, base: Path | None = None) -> RunWriter:
        base = OUTPUT_DIR if base is None else base
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_dir = base / "runs" / stamp
        suffix = 2
        while run_dir.exists():
            run_dir = base / "runs" / f"{stamp}-{suffix}"
            suffix += 1
        run_dir.mkdir(parents=True)
        return cls(run_dir)

    @classmethod
    def open(cls, run_id: str | None = None, base: Path | None = None) -> RunWriter:
        """Open an existing run, or the latest completed run when run_id is None."""
        base = OUTPUT_DIR if base is None else base
        if run_id is None:
            latest = load_json(base / "latest" / RUN_FILE, {})
            run_id = latest.get("run_id")
            if not run_id:
                raise FileNotFoundError(
                    "No completed run found in outputs/latest. Run the research pipeline first."
                )
        run_dir = base / "runs" / run_id
        if not run_dir.is_dir():
            raise FileNotFoundError(f"Run not found: {run_dir}")
        return cls(run_dir)

    def path(self, filename: str) -> Path:
        return self.run_dir / filename

    def write_json(self, filename: str, value: Any) -> Path:
        return dump_json(self.path(filename), value)

    def read_json(self, filename: str, default: Any = None) -> Any:
        return load_json(self.path(filename), default)

    def write_summary(
        self,
        channel_name: str,
        research_count: int,
        opportunities: list[Any],
        strategy: Any,
        territory: dict | None = None,
        warnings: Iterable[str] = (),
        intent: dict | None = None,
    ) -> Path:
        territory = territory or {}
        lines = [
            "# Run Summary",
            "",
            f"**Run:** {self.run_id}",
            f"**Channel:** {channel_name}",
        ]
        if intent:
            lines.append(f"**Your prompt:** {intent.get('prompt', '')}")
        lines += [
            f"**Research territory:** {territory.get('label', 'Unknown')} "
            f"({territory.get('confidence', 'unrated')} confidence)",
            f"**Research items:** {research_count}",
            f"**Opportunities:** {len(opportunities)}",
            "",
            "## Top opportunities",
            "",
        ]

        if not opportunities:
            lines.append("No opportunities were generated.")
        for index, item in enumerate(opportunities[:5], 1):
            lines.extend([
                f"### {index}. {item.topic}",
                f"- **Score:** {item.score} ({item.tier}, {item.evidence_count} matching items)",
                f"- **Angle:** {item.angle or 'not set'}",
                f"- **Rationale:** {item.rationale}",
                "",
            ])

        if strategy is not None:
            lines.extend([
                "## Strategy",
                "",
                f"- Content pillars: {len(strategy.pillars)}",
                f"- Series: {len(strategy.series)}",
                f"- Backlog items: {len(strategy.backlog)}",
                "",
            ])

        warnings = list(warnings)
        if warnings:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in warnings)
            lines.append("")

        target = self.path("run_summary.md")
        target.write_text("\n".join(lines), encoding="utf-8")
        return target

    def publish_latest(self) -> Path:
        """Copy this run to outputs/latest so tools can always read one place."""
        latest = self.run_dir.parent.parent / "latest"
        if latest.exists():
            shutil.rmtree(latest)
        shutil.copytree(self.run_dir, latest)
        return latest
