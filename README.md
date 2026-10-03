# Autonomous YouTube Agent

An AI-powered content operating system for researching, planning, producing and eventually learning from a faceless YouTube channel.

## What it does

Overseer is designed around a simple principle: **you decide what to study; the evidence decides the angle.** There are two ways in, and you can combine them:

| Input | Use it when | What Overseer does |
|---|---|---|
| **A prompt**: the topic and kind of video ("a calm 10-minute documentary on why Japanese trains are never late") | You already know what you want to make | Turns it into a brief and search queries, researches YouTube for that topic, and proposes evidence-backed angles in your format |
| **Reference channels** | You want to learn what works in a space | Infers the territory those channels cover, validates it across YouTube, and finds gaps |
| **Both** | You want your idea, informed by channels you admire | Your prompt sets the topic; the channels add evidence about style and audience |

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

With a prompt, the first two stages are replaced by **Prompt → brief and search queries → YouTube search for the topic**; everything from territory inference onwards is the same, and the requested format, tone, length, must-include and avoid lists carry through to the brief, script and QA.

The user's own channel configuration is **not** used to decide what a run studies. It only sets the voice and default format of produced videos (faceless, target length, claim policy), and a prompt's format and length override those defaults.

## Design principles

- **Niche-agnostic:** research is driven by your prompt or the reference channels you select, not a fixed genre list.
- **Evidence-first:** raw channel and video data is collected before strategy is generated.
- **Explainable:** territory inference exposes confidence and supporting evidence.
- **Universal:** architecture, finance, philosophy, history and other territories use the same pipeline.
- **Relative:** opportunity scores compare signals inside the collected research set; they are not predictions. Ideas no collected video supports are labelled hypotheses and ranked after validated ones.
- **Commercially aware:** audience demand and commercial intent are treated as separate signals.
- **Human-controlled:** a QA checklist must be cleared before a video is recorded as published.
- **Feedback-driven:** your own retention, views and CTR are fed back as channel history on future opportunities.

## Overseer local control center

Overseer runs **local-first** on Windows. Python 3.10 or newer is required.

### Setup

```powershell
.\scripts\setup_windows.ps1
```

Run it from inside a clone, or anywhere with `-Target C:\path\to\folder` to clone first.

### Keys

Copy `.env.example` to `.env` and add:

- `YOUTUBE_API_KEY` for public YouTube research.
- `ANTHROPIC_API_KEY` for territory inference, intelligence and production. Without it, those steps use clearly marked non-LLM fallbacks.
- `YOUTUBE_ACCESS_TOKEN` (optional) for `--learn`: an OAuth token with the `yt-analytics.readonly` scope for your channel.
- `CLAUDE_MODEL` / `CLAUDE_EFFORT` (optional) to override the default `claude-opus-5-5` at `medium` effort.

Never commit `.env`.

### Windows dashboard

```powershell
.\scripts\start_dashboard.ps1
```

Then open `http://localhost:3000`. The dashboard has four views (each has its own link, e.g. `#/production`):

- **New video:** describe your idea, pick the kind of video and length, and optionally add reference channels (`@handle`, `/channel/`, `/user/` or `/c/` URLs, with or without `https://`). The right-hand panel shows how Overseer read your brief, what it searched, the topic landscape and any warnings.
- **Opportunities:** angles ranked by evidence, filterable into validated ideas and hypotheses, each with its score breakdown and evidence. **Produce** creates the brief, script, production plan, thumbnails and QA checklist.
- **Production:** the brief, hook, outline, script sections, thumbnail concepts, QA checklist with claims to verify, and the commands for the next steps.
- **Learning:** your channel's analytics and what Overseer has learned from them.

It follows your system's light or dark setting (with a toggle), works on phones, and shows the last completed run after a restart.

### Command line

The CLI runs the same pipeline as the dashboard (`src/pipeline.py`).

```powershell
# 1. Research an idea (add --channel to combine with reference channels)
python main.py --prompt "A calm documentary on why Japanese trains are never late" --format documentary --length 8-15

#    ...or research reference channels on their own
python main.py --channel @channel1 --channel https://youtube.com/@channel2 --transcripts

# 2. Produce one of the listed opportunities (from the latest run)
python main.py --produce 2

# 3. Clear outputs/latest/qa_report.json, publish the video, then link it
python main.py --record-published https://youtu.be/VIDEO_ID

# 4. Later, learn from your channel's performance
python main.py --learn --analytics-start 2026-09-01 --analytics-end 2026-09-30 --ctr-csv "Table data.csv"
```

`--learn` uses the YouTube Analytics API for views, retention and subscribers. Thumbnail impressions and CTR are not available from that API, so import them with `--ctr-csv` from a YouTube Studio export (Advanced mode → Export → `Table data.csv`) or a YouTube Reporting API reach report.

Run `python main.py --help` for every option.

## Repository structure

```text
config/          Channel configuration (voice, format, audience fallbacks)
src/             Agent logic: research, intelligence, opportunity, strategy,
                 production, QA, learning; pipeline.py ties them together
web/             Dashboard served by overseer_server.py
research/        Optional local research notes (--local-research)
outputs/runs/    One folder per run; outputs/latest/ is the last completed run
data/            Channel memory, published-video registry, analytics (git-ignored)
docs/            Architecture notes, including the planned cloud design
tests/           Automated tests (python -m pytest)
main.py          CLI entry point
```

## Project status

### Phase 1 — Foundation
- [x] Channel configuration
- [x] Shared data models
- [x] Local research ingestion
- [x] Explainable opportunity scoring
- [x] Strategy generation
- [x] CLI entry point
- [x] Structured outputs
- [x] Test suite and CI

### Phase 2 — Intelligence
- [x] Live YouTube research adapter (with retries and quota handling)
- [x] Reference-channel research
- [x] Channel/video topic metadata
- [x] Territory inference
- [x] Audience intelligence
- [x] Hook and title pattern extraction, including transcript openings
- [ ] Reddit/search adapters
- [ ] Deeper competitor analysis
- [ ] Automated breakout detection
- [ ] Commercial intelligence enrichment

### Phase 3 — Production
- [x] Video brief generator
- [x] Script generation
- [x] Visual planning
- [x] Thumbnail brief generation
- [x] QA checklist and publish gate
- [ ] Voice generation adapter
- [ ] Video rendering adapter

### Phase 4 — Distribution
- [ ] YouTube upload integration
- [ ] Metadata generation
- [ ] Scheduling
- [x] Publishing safeguards (QA gate on `--record-published`)

### Phase 5 — Learning
- [x] Analytics data model and feedback loop
- [x] Topic performance memory, attached to new opportunities
- [x] Retention by topic and video length; CTR by title pattern (CTR via CSV import)
- [ ] RPM / revenue learning
- [ ] Affiliate conversion learning
- [ ] Automated strategy updates

## Output contract

Each run writes to `outputs/runs/<run id>/` and, when it completes, is copied to `outputs/latest/`:

- `run.json`: status, options (including your prompt), warnings, and which opportunity was produced
- `intent.json` (prompt runs): the brief Overseer read from your prompt, including the search queries it used
- `research_territory.json`
- `research.json`
- `intelligence.json` (when research was collected)
- `opportunities.json`: each with `score`, `tier` (`validated` or `hypothesis`), `evidence_count`, `opportunity_id` and any channel `history`
- `strategy.json`
- `run_summary.md`

Producing an opportunity adds `video_brief.json`, `script.json`, `production_plan.json`, `thumbnail_concepts.json` and `qa_report.json`. When an LLM step fails, its file still contains a fallback with a `fallback_reason` (or `error` for territory and intelligence) explaining why.

Persistent state lives in `data/`: `channel_memory.json`, `published.json` and `analytics.json`.

## Tech stack

Python, YAML, JSON, YouTube Data and Analytics APIs, and the Anthropic API (structured outputs).

## Learning loop

```text
Produced opportunity ──► QA cleared ──► Published video (--record-published)
                                               ↓
                     Views / retention (YouTube Analytics) + CTR (CSV import)
                                               ↓
                                     data/channel_memory.json (--learn)
                                               ↓
                      Channel history attached to matching new opportunities
```

The long-term goal is for Overseer to become a research and decision-support system that gets better from the user's own channel evidence without pretending that every high-view topic is automatically a good business opportunity.
