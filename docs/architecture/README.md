# Planned cloud architecture (not implemented)

This note replaces the `app/` scaffolding, `config/local.yaml`,
`config/cloud.yaml`, `vercel.json` and `api/health.py`, which described a
future cloud deployment but were never wired into the running code. Keeping
them as code made the repository look further along than it is. The design
intent is preserved here; `schema.sql` in this folder is the original table
layout, unchanged.

The working system today is local-first: `main.py` (CLI) and
`overseer_server.py` (dashboard) both run `src/pipeline.py`, and state lives in
`outputs/runs/`, `outputs/latest/` and `data/`.

## Pipeline steps

The cloud orchestrator was meant to run these steps in order, each behind its
own agent, stopping at the first failure:

```text
research → intelligence → opportunity → strategy → brief → script → production → thumbnail → qa
```

`src/pipeline.py` now implements all of them, including `qa`.

## Scheduled jobs

| Job | Cron (UTC) | Purpose |
|---|---|---|
| `daily_research` | `0 8 * * *` | Discover new audience and content signals |
| `opportunity_refresh` | `30 8 * * *` | Re-score opportunities using fresh research |
| `weekly_strategy` | `0 9 * * 1` | Refresh pillars, series and content backlog |
| `performance_learning` | `0 10 * * *` | Collect channel performance and update memory |

Locally, the equivalents are a Windows Task Scheduler entry running
`python main.py --channels-file channels.txt` and another running
`python main.py --learn --analytics-start ... --analytics-end ...`.

## Runtime profiles

Both profiles kept `human_approval_before_publish: true` and `publishing: false`.

| | Local | Cloud |
|---|---|---|
| Storage | local filesystem (`data/assets`) | managed object storage (S3, R2, Supabase Storage…) behind an `upload` / `signed_url` interface |
| Database | SQLite (`data/agent.db`) | managed Postgres |
| Scheduler | local scheduler | managed scheduler |

## Before building it

- **Long runs don't fit serverless limits.** A research run makes dozens of
  YouTube calls and several long LLM calls. Use a worker with a job queue, not
  request-scoped functions.
- **Move state into the database.** `outputs/runs/<id>/*.json` and
  `data/*.json` map directly onto the `agent_run`, `research_item`,
  `opportunity`, `content_asset` and `video_performance` tables in
  `schema.sql`.
- **Add authentication.** The local dashboard relies on binding to
  127.0.0.1; a hosted one must not.
