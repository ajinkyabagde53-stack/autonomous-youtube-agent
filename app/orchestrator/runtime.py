from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class AgentRun:
    run_id: str
    started_at: str
    status: str = "created"
    completed_steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)


class CloudOrchestrator:
    """Cloud-friendly workflow coordinator.

    The orchestrator contains no local media-processing assumptions. Each
    expensive capability can be implemented behind an API adapter and invoked
    by a scheduled cloud worker.
    """

    def __init__(self, agents: dict[str, Callable[..., Any]]) -> None:
        self.agents = agents

    def start(self, run_id: str) -> AgentRun:
        return AgentRun(
            run_id=run_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            status="running",
        )

    def execute(self, run: AgentRun, steps: list[str], context: dict[str, Any]) -> AgentRun:
        for step in steps:
            agent = self.agents.get(step)
            if not agent:
                run.errors.append(f"No agent registered for step: {step}")
                run.status = "failed"
                break

            try:
                run.outputs[step] = agent(context)
                run.completed_steps.append(step)
            except Exception as exc:
                run.errors.append(f"{step}: {type(exc).__name__}: {exc}")
                run.status = "failed"
                break

        if run.status != "failed":
            run.status = "completed"

        return run
