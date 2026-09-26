from __future__ import annotations

from typing import Any

DEFAULT_PIPELINE = [
    "research",
    "intelligence",
    "opportunity",
    "strategy",
    "brief",
    "script",
    "production",
    "thumbnail",
    "qa",
]


def build_pipeline(overrides: list[str] | None = None) -> list[str]:
    return overrides or DEFAULT_PIPELINE


def run_pipeline(orchestrator: Any, run_id: str, context: dict[str, Any], steps: list[str] | None = None):
    run = orchestrator.start(run_id)
    return orchestrator.execute(
        run,
        build_pipeline(steps),
        context,
    )
