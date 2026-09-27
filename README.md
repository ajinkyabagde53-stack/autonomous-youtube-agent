# Autonomous YouTube Agent

An AI-powered content operating system for researching, planning, producing and eventually learning from a faceless YouTube channel.

## What it does

Overseer is designed around a simple principle: **the user chooses what to study by selecting reference YouTube channels; Overseer infers the research territory from the evidence.**

The system is intentionally niche-agnostic. The same workflow can research architecture, finance, philosophy, history, science, business, gaming, or any other YouTube territory without changing the dashboard.

## Research architecture

```text
Reference YouTube Channels
        ↓
Channel Intelligence
  • Channel positioning
  • Descriptions
  • Recent videos
  • Views / engagement
  • Publishing patterns
        ↓
Territory Inference
  • Primary territory
  • Sub-territories
  • Observed audience
  • Confidence
  • Evidence
        ↓
Wider YouTube Validation
        ↓
Content Landscape
  • What's winning?
  • Breakout signals
  • Common formats
  • Saturated areas
  • Emerging topics
  • Missing topics
        ↓
Gap + Winner Analysis
        ↓
Commercial Intelligence
        ↓
Opportunity Engine
        ↓
Top Opportunities
        ↓
User Selects
        ↓
Content Production
```

The user's own channel configuration is **not** used to decide what territory a reference-channel run should study.

## Design principles

- **Niche-agnostic:** research is driven by the selected reference channels, not a fixed genre list.
- **Evidence-first:** raw channel and video data is collected before strategy is generated.
- **Explainable:** territory inference exposes confidence and supporting evidence.
- **Universal:** architecture, finance, philosophy, history and other territories use the same pipeline.
- **Relative:** opportunity scores compare signals inside the collected research set; they are not predictions.
- **Commercially aware:** audience demand and commercial intent are treated as separate signals.
- **Human-controlled:** publishing remains approval-gated until explicitly automated.
- **Feedback-driven:** future versions will feed the user's own CTR, retention, views, RPM and conversion data back into the system.

## Overseer local control center

Overseer runs **local-first** on Windows.

### Research setup

Paste one YouTube channel URL per line:

```text
https://youtube.com/@channel1
https://youtube.com/@channel2
https://youtube.com/@channel3
```

Overseer then:

1. Collects public channel metadata.
2. Collects recent public videos and performance signals.
3. Infers the shared research territory.
4. Validates that territory against wider YouTube.
5. Extracts winning patterns, gaps and audience signals.
6. Generates explainable opportunity candidates.

### Live research keys

Copy `.env.example` to `.env` and add:

- `YOUTUBE_API_KEY` for public YouTube research.
- `ANTHROPIC_API_KEY` for territory inference and semantic intelligence.

Never commit `.env`.

### Windows dashboard

```powershell
git pull
.\scripts\start_dashboard.ps1
```

Then open `http://localhost:3000`.

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
- [x] Live YouTube research adapter
- [x] Reference-channel research
- [x] Channel/video topic metadata
- [x] Territory inference foundation
- [x] Audience intelligence foundation
- [x] Hook and title pattern extraction foundation
- [ ] Reddit/search adapters
- [ ] Deeper competitor analysis
- [ ] Automated breakout detection
- [ ] Commercial intelligence enrichment

### Phase 3 — Production
- [x] Video brief generator
- [x] Script generation
- [x] Visual planning
- [x] Thumbnail brief generation
- [ ] Voice generation adapter
- [ ] Video rendering adapter

### Phase 4 — Distribution
- [ ] YouTube upload integration
- [ ] Metadata generation
- [ ] Scheduling
- [ ] Publishing safeguards

### Phase 5 — Learning
- [x] Analytics data model and feedback-loop foundation
- [x] Topic performance memory
- [ ] CTR and retention analysis
- [ ] RPM / revenue learning
- [ ] Affiliate conversion learning
- [ ] Automated strategy updates

## Output contract

A run produces:

- `outputs/research.json`
- `outputs/research_territory.json`
- `outputs/opportunities.json`
- `outputs/strategy.json`
- `outputs/run_summary.md`

## Tech stack

Python, YAML, JSON, YouTube Data API, pluggable research adapters, and LLM integrations.

## Future learning loop

```text
Your Videos
   ↓
Views / CTR / Retention / Subscribers
   ↓
RPM / Revenue / Affiliate Clicks
   ↓
Overseer Memory
   ↓
Future Opportunity Analysis
```

The long-term goal is for Overseer to become a research and decision-support system that gets better from the user's own channel evidence without pretending that every high-view topic is automatically a good business opportunity.
