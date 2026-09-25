# Autonomous YouTube Agent

An AI-powered content operating system for building and scaling a YouTube channel from research to performance feedback.

## What it does

This system moves beyond “generate a script” workflows. It is designed as a modular pipeline:

1. Configure a channel
2. Research the audience and content landscape
3. Extract topics, pain points, hooks and patterns
4. Score content opportunities
5. Build content pillars and a publishing backlog
6. Generate video briefs and production assets
7. Publish with human approval
8. Capture channel performance
9. Feed performance back into future content decisions

## Architecture

```text
Channel Config
     |
     v
Research Agents
     |
     +--> Audience Intelligence
     +--> Content Landscape
     +--> Competitor Signals
     |
     v
Opportunity Engine
     |
     v
Strategy Agent
     |
     +--> Content Pillars
     +--> Series
     +--> Backlog
     |
     v
Production Agents
     |
     +--> Video Brief
     +--> Script
     +--> Visual Plan
     +--> Thumbnail Brief
     |
     v
Publishing / YouTube
     |
     v
Analytics Agent
     |
     +----------------------+
     |                      |
     +---- Learning Loop ---+
```

## Design principles

- **Niche-agnostic:** channel configuration is separated from agent logic.
- **Evidence-first:** research becomes structured data before strategy is generated.
- **Modular:** each agent can be replaced or upgraded independently.
- **Explainable:** opportunity scores expose the signals behind an idea.
- **Human-controlled:** publishing remains approval-gated until explicitly automated.
- **Feedback-driven:** channel performance becomes input to future decisions.

## Repository structure

```text
config/          Channel and prompt configuration
src/             Core agent logic and shared models
research/        Local research inputs and future source caches
outputs/         Machine-readable and human-readable run artifacts
tests/           Automated tests
main.py          Pipeline entry point
```

## Project status

### Phase 1 — Foundation
- [x] Channel configuration
- [x] Shared data models
- [x] Local research ingestion
- [x] Explainable opportunity scoring
- [x] Strategy generation scaffold
- [x] CLI entry point
- [x] Structured outputs
- [x] Basic tests

### Phase 2 — Intelligence
- [ ] Live YouTube research
- [ ] Transcript ingestion
- [ ] Audience question mining
- [ ] Reddit/search adapters
- [ ] Competitor analysis
- [ ] Hook and title pattern extraction

### Phase 3 — Production
- [ ] Video brief generator
- [ ] Script generation
- [ ] Visual planning
- [ ] Thumbnail brief generation
- [ ] Voice generation adapter
- [ ] Video rendering adapter

### Phase 4 — Distribution
- [ ] YouTube upload integration
- [ ] Metadata generation
- [ ] Scheduling
- [ ] Publishing safeguards

### Phase 5 — Learning
- [ ] YouTube Analytics ingestion
- [ ] CTR and retention analysis
- [ ] Topic performance memory
- [ ] Automated strategy updates

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

Configure `config/channel.yaml` before running the pipeline.

## Output contract

A run produces:

- `outputs/research.json`
- `outputs/opportunities.json`
- `outputs/strategy.json`
- `outputs/run_summary.md`

## Tech stack

Python, YAML, JSON, pluggable data-source adapters, and LLM integrations.

## Roadmap

The repository starts with a deterministic, testable core. External APIs and expensive generation steps are added as adapters rather than tightly coupling them to orchestration.
