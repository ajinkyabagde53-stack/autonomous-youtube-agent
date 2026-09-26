from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    schedule: str
    purpose: str


JOBS = [
    ScheduledJob(
        name="daily_research",
        schedule="0 8 * * *",
        purpose="Discover new audience and content signals.",
    ),
    ScheduledJob(
        name="opportunity_refresh",
        schedule="30 8 * * *",
        purpose="Re-score opportunities using fresh research.",
    ),
    ScheduledJob(
        name="weekly_strategy",
        schedule="0 9 * * 1",
        purpose="Refresh pillars, series and content backlog.",
    ),
    ScheduledJob(
        name="performance_learning",
        schedule="0 10 * * *",
        purpose="Collect channel performance and update memory.",
    ),
]
