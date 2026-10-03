# Overseer code review: weaknesses, fixes and remaining work

**Repository:** `ajinkyabagde53-stack/autonomous-youtube-agent`, `main` branch as downloaded on 2026-10-03
**Scope:** every Python module, config file, script and test, plus the dashboard (HTML/JS/CSS)
**Status:** all 50 findings fixed across two passes; a third pass added prompt input and redesigned the dashboard; 130 automated tests pass

---

## Contents

1. [Summary](#1-summary)
2. [How this was verified](#2-how-this-was-verified)
3. [All findings at a glance](#3-all-findings-at-a-glance)
4. [Findings in detail](#4-findings-in-detail)
5. [Changes by file](#5-changes-by-file)
6. [Behaviour changes and migration](#6-behaviour-changes-and-migration)
7. [Remaining limitations and suggestions](#7-remaining-limitations-and-suggestions)
8. [How to verify on your machine](#8-how-to-verify-on-your-machine)
9. [Pass 3: prompt input and dashboard redesign](#9-pass-3-prompt-input-and-dashboard-redesign)

---

## 1. Summary

The research → opportunity → strategy core was well built and honest about uncertainty. Five structural problems undercut it:

1. **The LLM layer failed without telling anyone.** A reply that wasn't bare JSON became `{"raw": ...}`, every downstream fallback treated that as success, and briefs, scripts and production plans were built from nothing.
2. **There were two pipelines with opposite philosophies.** The CLI researched the configured niche; the dashboard researched reference channels. Only the CLI could produce videos, and those prompts ignored what had been researched.
3. **Opportunity scoring favoured made-up ideas.** A gap the LLM produced with no supporting videos scored as "no competition" and tended to rank first. Topic matching was loose enough that "how" or "best" matched almost everything.
4. **The learning loop was scaffolding only.** Memory was written but never read, topic signals were always empty, title patterns were computed on video IDs, and two of the requested analytics metrics don't exist.
5. **The dashboard showed invented numbers.** "Channel health 78/100" and "↑ 12% vs last month" were hardcoded, the approve buttons did nothing, and the video checklist was always ticked.

**Pass 1** fixed (1) and (2). **Pass 2** fixed everything else. The system now has one pipeline, a working research → produce → QA → publish → learn loop, a dashboard that only shows real state, and a test suite that runs in CI.

| Status | Count |
|---|---|
| Fixed in pass 1 | 17 |
| Fixed in pass 2 | 33 |
| Open | 0 (see [section 7](#7-remaining-limitations-and-suggestions) for limitations and roadmap items) |

---

## 2. How this was verified

The review machine is a managed work laptop with no Python and no permission to install it, so tests ran in **Pyodide** (CPython 3.12 compiled to WebAssembly) inside the app's built-in browser. Nothing was installed on the laptop.

| Check | Result |
|---|---|
| Original test suite on the original code | **1 of 4 tests failing** (see W50) |
| Full suite after passes 1 and 2 | **107 passed**, stable across repeated runs |
| Full suite after pass 3 | **130 passed** |
| Every `.py` file parsed with the Python 3.10 grammar | 38 files, no problems |
| `python main.py --help` | builds correctly |
| Redesigned dashboard with mock `/api/status` data, at 375px, 1100px and 1280px wide | no horizontal overflow, no text under 12px, no tap target under 32px (most are 44px) |
| Text contrast, every visible text element in all four views | 323 elements checked; all meet WCAG AA in both dark and light themes |
| Composer behaviour (validation, example chips, mode hints, server errors) | works; one bug found and fixed (see section 9) |
| Anthropic SDK parameters (`output_config`, `fallbacks="default"`, `betas`) | confirmed against the published `anthropic` 1.x source |
| YouTube Analytics metric names | confirmed against Google's metrics reference and revision history |

**Not verified here:**

- **Live API calls.** The Anthropic SDK can't install under Pyodide (it needs a compiled `jiter` package), so tests stub it. YouTube and Analytics calls are tested with mocked HTTP. Run one real pipeline with your keys ([section 8](#8-how-to-verify-on-your-machine)).
- **The real HTTP server.** Pyodide has no sockets or threads, so the request handler was tested with simulated requests and a fake thread. The `ThreadingHTTPServer` wiring itself is unchanged from the original.
- **The PowerShell scripts and the CI workflow** weren't executed.

---

## 3. All findings at a glance

Severity: **Critical** = silently wrong results · **High** = a feature doesn't do what it claims · **Medium** = robustness, cost or maintainability · **Low** = polish.

| ID | Area | Finding | Severity | Fixed in |
|---|---|---|---|---|
| W1 | LLM | Replies that aren't clean JSON become `{"raw": ...}` and pass as success | Critical | Pass 1 |
| W2 | LLM | `max_tokens=3000` truncates long outputs | High | Pass 1 |
| W3 | LLM | No check for refusals or truncation | Medium | Pass 1 |
| W4 | LLM | Outdated default model | Low | Pass 1 |
| W5 | Config | CLI never loads `.env`; runs keyless without warning | Critical | Pass 1 |
| W6 | LLM | `ThumbnailAgent` has no fallback | Low | Pass 1 |
| W7 | Architecture | CLI and dashboard are two different pipelines | High | Pass 1 |
| W8 | Architecture | Brief and script prompts ignore the researched territory | High | Pass 1 |
| W9 | Architecture | Four orchestrators plus unused scaffolding and config | Medium | Pass 2 |
| W10 | Architecture | Two YouTube HTTP clients | Low | Pass 2 |
| W11 | Opportunity | Object-shaped gap candidates become `"{'topic': ...}"` topic names | Critical | Pass 2 |
| W12 | Opportunity | Topics with zero evidence get high scores | Critical | Pass 2 |
| W13 | Opportunity | Any shared word counts as a topic match | Medium | Pass 2 |
| W14 | Opportunity | The angle is placeholder text | Low | Pass 2 |
| W15 | Opportunity | With no research, config pain points pose as opportunities | Medium | Pass 2 |
| W16 | Research | `research/README.md` is treated as research | High | Pass 1 |
| W17 | Research | CLI searches with full pain-point sentences (~900 quota units) | Medium | Pass 1 |
| W18 | Research | Transcripts are fetched but never used | High | Pass 2 |
| W19 | Research | Intelligence only sees the first 60 items in arrival order | Medium | Pass 2 |
| W20 | Research | URL parsing rejects URLs without a scheme and `/c/` URLs | Medium | Pass 2 |
| W21 | Research | No retry or quota handling for YouTube | Medium | Pass 2 |
| W22 | Research | Error messages can contain the API key | Low | Pass 2 |
| W23 | Learning | Topic memory is always empty | High | Pass 2 |
| W24 | Learning | Memory is never loaded or applied | High | Pass 2 |
| W25 | Learning | Video "titles" are actually video IDs | High | Pass 2 |
| W26 | Learning | `format_signals` is never populated | Low | Pass 2 |
| W27 | Learning | Analytics requests two metrics that don't exist | High | Pass 2 |
| W28 | Learning | Memory path relative to the current directory | Low | Pass 2 |
| W29 | Strategy | Pillar matching almost never matches | Medium | Pass 2 |
| W30 | Production | Fact-check queues are never acted on; no QA step | Medium | Pass 2 |
| W31 | Production | Production plan built from a script with no sections | Low | Pass 1 |
| W32 | CLI | Flags silently ignored | Medium | Pass 1 |
| W33 | CLI | Outputs written late; a crash loses paid-for research | Medium | Pass 1 |
| W34 | CLI | No exit codes | Low | Pass 1 |
| W35 | CLI | Unused import | Low | Pass 1 |
| W36 | Outputs | Each run overwrites the last; stale files remain | Medium | Pass 2 |
| W37 | Outputs | No logging | Low | Pass 2 |
| W38 | Dashboard | Any website you visit can start a run | Medium | Pass 2 |
| W39 | Dashboard | Two quick clicks can start two runs | Low | Pass 2 |
| W40 | Dashboard | `research_mode` accepted but unused | Low | Pass 2 |
| W41 | Dashboard | The approve arrow does nothing | Medium | Pass 2 |
| W42 | Dashboard | Vercel deploy serves a UI whose API doesn't exist | Medium | Pass 2 |
| W43 | Dashboard | A failure in wider validation crashes the run | Medium | Pass 1 |
| W44 | Dashboard | All-channels-failed runs "complete" with config ideas | Medium | Pass 1 |
| W45 | Dashboard | Warnings are tracked but not shown | Low | Pass 2 |
| W46 | Tests | Thin coverage | Medium | Pass 2 |
| W47 | Tests | Tests depend on the real `config/channel.yaml` | Low | Pass 2 |
| W48 | Tooling | No CI; setup script hard-codes `D:\AI` | Low | Pass 2 |
| W49 | Dashboard | **New:** hardcoded fake metrics and always-ticked checklist | High | Pass 2 |
| W50 | Tests | **New:** an original test could never pass | Medium | Pass 2 |

---

## 4. Findings in detail

Each entry gives the problem and what was done. File references point to the current code.

### A. LLM layer (pass 1)

#### W1. Non-JSON replies passed as success (Critical)

- **Problem:** `json.loads` failed whenever Claude wrapped its answer in a code fence or added a sentence, and the client returned `{"raw": text}`. Agents did `return result or {fallback}`; a non-empty dict counts as true, so fallbacks never ran. Briefs held only `raw`, scripts were written from that, production plans had zero scenes, and nothing reported an error.
- **Fix:** `src/llm.py` now uses structured outputs (`output_config.format` with a JSON schema per agent), parses defensively, checks required keys, and raises `LLMError` on any failure. Each agent catches it and returns an explicit fallback carrying `fallback_reason`; the pipeline lists each fallback as a warning.

#### W2, W3. Truncation and refusals (High, Medium)

- **Problem:** `max_tokens=3000` was too small for scripts once thinking tokens count, and `stop_reason` was never checked.
- **Fix:** calls stream with `max_tokens=32000`; `max_tokens` and `refusal` stop reasons raise clear errors; refusal fallbacks (`fallbacks="default"`) re-run declined requests on Anthropic's recommended fallback model.

#### W4. Outdated default model (Low)

Default changed to `claude-opus-5-5` at `medium` effort; override with `CLAUDE_MODEL` / `CLAUDE_EFFORT`. Opus 5.5 costs $4 / $20 per million input/output tokens; `claude-sonnet-5-5` is $2 / $10. Empty `.env` values fall back to the defaults instead of sending an empty model name.

#### W5. `.env` never loaded by the CLI (Critical)

`main.py` and `overseer_server.py` call `load_dotenv()`. A missing `YOUTUBE_API_KEY` stops the run with an error; a missing `ANTHROPIC_API_KEY` produces one explicit warning.

#### W6. Thumbnail agent without a fallback (Low)

Returns `{"concepts": [], "selection_notes": "", "fallback_reason": ...}` on failure.

### B. Architecture

#### W7, W8. Two pipelines; production ignored the territory (High, pass 1)

- **Problem:** the CLI researched the configured niche and could produce; the dashboard researched reference channels and could not. Brief and script prompts always assumed the configured "AI tools" channel.
- **Fix:** both entry points call `src/pipeline.py`. `src/prompting.py:production_context` makes the researched territory decide subject and audience; the channel config supplies only voice and format.

#### W9, W10. Unused code and config (Medium, Low; pass 2)

- **Problem:** `src/orchestrator.py`, `app/` (orchestrator, jobs, storage, schema), `config/local.yaml`, `config/cloud.yaml`, `config/prompts.yaml`, `vercel.json` and `api/health.py` were never used. `prompts.yaml` was the worst case: editing it changed nothing. `src/youtube.py` duplicated the YouTube client.
- **Fix:** removed. The cloud design intent (step order, job schedule, runtime profiles, table layout) is preserved in `docs/architecture/README.md` with the original `schema.sql` beside it.

### C. Opportunity engine (pass 2)

#### W11. Garbage topic names (Critical)

- **Problem:** `str(dict)` turned object-shaped gap candidates into topics like `"{'topic': ...}"`.
- **Fix:** gap candidates are now a schema-defined object (`topic`, `angle`, `supporting_item_ids`, `evidence`), and `OpportunityEngine` accepts strings or objects and skips anything else.

#### W12. Unsupported ideas ranked first (Critical)

- **Problem:** a candidate with zero matching videos got `competition_gap = 1.0` ("no competition") and neutral demand, so it outranked topics with real evidence.
- **Fix:**
  - Every opportunity now carries `evidence_count` and a `tier`: `validated` (backed by collected videos) or `hypothesis`.
  - The score is multiplied by an evidence factor (0.6 with no evidence, rising to 1.0 at three or more matching videos).
  - Unsupported candidates get a neutral 0.5 competition gap ("unknown"), not 1.0.
  - Ranking puts validated opportunities before hypotheses.

#### W13. Loose matching (Medium)

- **Problem:** a candidate matched a video if any word of three or more letters overlapped.
- **Fix:** `src/text.py` drops stopwords ("how", "best", "your", "video"…) and a video must cover at least half of the topic's meaningful words. The analyst's cited `supporting_item_ids` are always included.

#### W14. Placeholder angle (Low)

Angles now come from the analyst (`angle` in each gap candidate). Title-derived candidates leave the angle empty rather than inventing one; the brief writes it.

#### W15. Config seeds posing as findings (Medium)

Seeds from `config/channel.yaml` are always the `hypothesis` tier, the pipeline warns when it falls back to them, and the dashboard labels them "HYPOTHESIS · NEEDS VALIDATION".

### D. Research

#### W16, W17. README as research; wasteful searches (pass 1)

`README.md` files are skipped and local notes are opt-in (`--local-research`). Niche searching with pain-point sentences (~900 quota units per run) was replaced by three searches on the inferred territory (~300 units).

#### W18. Transcripts discarded (High, pass 2)

`IntelligenceAgent.analyze` now sends a `transcript_excerpt` (the first 1,500 characters, which usually carry the hook and promise) for each sampled video that has one, and the prompt tells the analyst to use it.

#### W19. Arbitrary sample (Medium, pass 2)

`sample_for_analysis` builds the 60-video sample by alternating sources (each reference channel and the wider-YouTube set) and, within each source, alternating most-viewed and most-recent videos. Each sampled video carries its index as `id`, which is what the analyst cites in `supporting_item_ids`.

#### W20. URL parsing (Medium, pass 2)

Accepts `@handle`, URLs without `https://`, and `/c/CustomName` URLs (resolved with a channel search, which costs 100 quota units, so handles are still preferred). Trailing paths like `/videos` are ignored.

#### W21, W22. Retries, quota and key leaks (Medium, Low; pass 2)

- `ResearchAgent._get_json` retries 429 and 5xx responses and network errors three times with backoff.
- `quotaExceeded` / `dailyLimitExceeded` raise `YouTubeQuotaError` with a plain-language message, and the pipeline stops instead of failing every remaining channel.
- Error messages are built from the API's JSON error, never from the request URL, so the key can't leak. The `requests`-based client that leaked it was removed.

### E. Learning loop (pass 2)

The full loop now works: **produce → clear QA → publish → `--record-published` → `--learn` → history on new opportunities.**

#### W23. Topic memory always empty (High)

- **Problem:** nothing recorded which video came from which opportunity.
- **Fix:** each opportunity has a stable `opportunity_id`; `main.py --record-published VIDEO` links a published video to the run's produced opportunity in `data/published.json` (`PublishedRegistry`), and `--learn` uses that mapping to build per-topic retention.

#### W24. Memory never applied (High)

The pipeline loads `data/channel_memory.json` and calls `LearningAgent.apply_to_opportunities` before saving opportunities. Matching topics (exact, or ≥60% word overlap in both directions) get a "Channel history" evidence line and a `history` field. **Scores are not changed**, so history never hides how a score was made; the dashboard shows it as a separate tag.

#### W25. Titles were video IDs (High)

`YouTubeAnalyticsAdapter` now fetches real titles and durations from the Data API (`videos.list`), using `YOUTUBE_API_KEY` or, failing that, the OAuth token. Videos whose details can't be fetched are left out of title signals, with a note.

#### W26. Empty format signals (Low)

`format_signals` now holds retention per length bucket: 60s or less, 1–8 min, 8–20 min, over 20 min.

#### W27. Metrics that don't exist (High)

- **Problem:** the request asked for `impressions` (the pre-2016 name for *ad* impressions, a monetary metric) and `impressionsCtr` (not a metric). The API would reject the request. `dimensions=video` also requires `maxResults`.
- **Verified:** per Google's documentation, thumbnail impressions and CTR are not available from Analytics API `reports.query`. Since January 2026 they exist only in Reporting API bulk "reach" reports (`video_thumbnail_impressions`, `video_thumbnail_impressions_ctr`).
- **Fix:** the query uses only valid metrics (views, likes, comments, shares, subscribersGained, estimatedMinutesWatched, averageViewDuration, averageViewPercentage) with `maxResults=200`, and maps columns by header name instead of position. CTR comes in through `--ctr-csv`, which reads a YouTube Studio export or a reach report. When no CTR is imported, title patterns compare views instead, and the memory says so.

#### W28. Path inconsistency (Low)

Persistent state now lives in `data/` resolved from the repo root, like `outputs/`, and `data/` is git-ignored. **Migration:** an old `outputs/channel_memory.json` is not read; it was always empty because of W23, so nothing is lost.

### F. Strategy and production

#### W29. Empty pillars (Medium, pass 2)

Pillars now come from the researched territory's sub-territories (falling back to config pillars, with the source recorded), and each opportunity is assigned to the pillar sharing the most words with its topic and angle.

#### W30. No QA (Medium, pass 2)

New `src/qa.py` writes `qa_report.json` after production:

- every claim from `claims_to_verify` and `fact_check_queue`, each with `verified: false` and an empty `source`;
- automated checks: model-generated brief and script (not fallbacks), title and hook present, sections with narration, length within 50% of the target, thumbnail text of five words or fewer.

`--record-published` refuses while any check fails or any claim lacks `verified: true` and a source, unless you pass `--force`.

#### W31. Empty production plans (Low, pass 1)

Skipped with a warning when the script has no sections.

### G. CLI and outputs

#### W32–W35. Flag handling, late writes, exit codes, unused import (pass 1)

All flag combinations are validated (pass 2 extended this to the new flags), each artifact is written as soon as it exists, `main()` returns 0 or 1, and the unused import is gone.

#### W36. Runs overwrote each other (Medium, pass 2)

`src/output.py:RunWriter` writes each run to `outputs/runs/<UTC timestamp>/`, with a `run.json` recording status, options, warnings and what was produced. Completed runs are copied to `outputs/latest/`; failed runs stay in `runs/` marked `failed` and don't replace `latest/`. Producing an opportunity clears that run's previous production files first.

#### W37. No logging (Low, pass 2)

The pipeline logs each step and warning through `logging`, configured from `LOG_LEVEL`.

### H. Dashboard and server (pass 2)

#### W38. Cross-site requests (Medium)

POSTs must be `Content-Type: application/json` (forcing a CORS preflight the server never approves), any `Origin` header must be localhost, every request's `Host` must be `localhost` or `127.0.0.1` (blocking DNS rebinding), bodies over 64 KB are rejected, and invalid `Content-Length` returns 400 instead of crashing.

#### W39. Double starts (Low)

`start_job` claims the running slot under a lock before starting the thread. All `STATE` updates and reads go through the same lock.

#### W40. `research_mode` (Low)

Removed from the API and state.

#### W41. Dead approve button (Medium)

The → button on each opportunity calls the new `POST /api/produce`, which runs brief → script → production plan → thumbnails → QA for that opportunity (`produce_from_run`). The same function backs `main.py --produce N`.

#### W42. Broken Vercel deploy (Medium)

`vercel.json` and `api/` removed; see W9 and `docs/architecture/README.md`.

#### W43, W44. Validation crashes; seed-idea runs (pass 1)

Wider-validation failures are warnings; runs where no channel can be collected fail with each channel's error.

#### W45. Warnings hidden (Low)

A warnings panel under the run status lists every warning.

#### W49. Fake dashboard data (High, new in pass 2)

- **Problem:** the "Channel health 78 / 100", "↑ 12% vs last month" and "Learning active" card was hardcoded; the video workspace always showed brief, script and plan as done; "Review & approve" and "Refresh" only showed a toast; "Run cost" always said "API"; the greeting always said "Good evening".
- **Fix:**
  - The health card is replaced by a **Learning memory** card showing videos analysed, topics linked and last update.
  - The video workspace shows the real produced opportunity: title, thumbnail text, checklist, QA status and any fallbacks.
  - The performance section shows real analytics with its date range, or "—".
  - Refresh actually refreshes; the run tile shows the run ID; the greeting follows the time of day.
  - After a restart, the server restores the last completed run so ideas can still be produced.

### I. Tests and tooling (pass 2)

#### W46, W47. Coverage and fixtures (Medium, Low)

107 tests across 10 files cover the LLM client, opportunity scoring, intelligence sampling, research (URL resolution, retries, quota, key safety), analytics (column mapping, durations, CSV import), learning and memory, strategy, QA, run folders, the full pipeline (offline and with a scripted LLM), CLI validation and the QA publish gate, and the server (CSRF, Host checks, run lock, produce validation, restore). Tests use `tests/fixtures/channel.yaml`, and `tests/conftest.py` redirects `outputs/` and `data/` to a temp folder and clears API keys, so tests can't touch real state or spend quota.

#### W48. CI and setup (Low)

`.github/workflows/tests.yml` runs the suite on Python 3.10 and 3.12 for every push and pull request. `scripts/setup_windows.ps1` works from inside any clone (or clones to `-Target`), checks for Python 3.10+, and no longer creates unused folders.

#### W50. An original test could never pass (Medium, new in pass 2)

`test_research_signals_change_opportunity` asserted that an item's `topics` value ("test topic") becomes an opportunity, but the engine has always built candidates from titles. Running the original suite confirmed it: **1 failed, 3 passed**. The test now asserts the real behaviour.

---

## 5. Changes by file

Compared with the downloaded repository: 47 files changed or added, 18 files removed.

### New

| File | Purpose |
|---|---|
| `src/pipeline.py` | The single pipeline: `run_pipeline` (research → plan, optional production) and `produce_from_run` (production for any opportunity of a saved run) |
| `src/prompting.py` | `production_context`: territory decides subject and audience, config decides voice and format |
| `src/qa.py` | QA checklist and `unresolved_claims` for the publish gate |
| `src/text.py` | Stopword-aware tokenising and coverage matching |
| `docs/architecture/README.md`, `schema.sql` | Preserved cloud design |
| `.github/workflows/tests.yml`, `pytest.ini` | CI |
| `tests/conftest.py`, `tests/fakes.py`, `tests/fixtures/channel.yaml` | Test isolation and shared fakes |
| `tests/test_analytics.py`, `test_intelligence.py`, `test_llm.py`, `test_main.py`, `test_pipeline.py`, `test_server.py`, `test_strategy_qa_output.py` | New tests |

### Changed

| File | Change |
|---|---|
| `src/llm.py` | Structured outputs, streaming, stop-reason checks, refusal fallbacks, `LLMError`, schema helpers |
| `src/models.py` | `Opportunity` gains `evidence_count`, `opportunity_id`, `history`, `tier`, evidence-capped `score`, `to_dict` / `from_dict` |
| `src/opportunity.py` | Rewritten: cited evidence, strict matching, tiers, real angles, stable IDs |
| `src/intelligence.py` | Schemas, balanced sampling with IDs, transcript excerpts, object gap candidates, honest territory fallback |
| `src/brief.py`, `src/script.py`, `src/thumbnail.py` | Schemas, territory-aware prompts, explicit fallbacks |
| `src/strategy.py` | Territory pillars, word-overlap assignment, tier and ID in the backlog |
| `src/research.py` | URL normalisation, `/c/` URLs, retries, quota error, safe error messages, README skip |
| `src/analytics.py` | More fields; richer summary for the dashboard |
| `src/youtube_analytics.py` | Valid metrics, `maxResults`, header-based mapping, real titles and durations, CTR CSV import |
| `src/learning.py` | Topic, title and format signals; notes; fuzzy history matching that doesn't change scores |
| `src/memory.py` | `data/` paths, tolerant loading, `PublishedRegistry`, `parse_video_id` |
| `src/output.py` | `RunWriter` (run folders, `latest/`, summaries), `data/` helpers |
| `main.py` | Rewritten CLI: research, `--produce`, `--record-published` with QA gate, `--learn --ctr-csv`, logging |
| `overseer_server.py` | Shared pipeline, `/api/produce`, CSRF and Host checks, run lock, locked state, restore on start, real production and learning data |
| `web/index.html`, `web/app.js`, `web/styles.css` | Real data only, warnings panel, tiers and history tags, working produce button, live workspace and analytics |
| `tests/test_learning.py`, `test_opportunity.py`, `test_research.py` | Extended; W50 fixed |
| `README.md`, `research/README.md`, `.env.example`, `.gitignore`, `requirements.txt`, `scripts/setup_windows.ps1` | Documentation, keys, `data/` ignore, `anthropic>=1.0,<2`, setup |

### Removed

`src/orchestrator.py`, `src/youtube.py`, `app/` (10 files; `schema.sql` moved to `docs/architecture/`), `api/` (2 files), `vercel.json`, `config/local.yaml`, `config/cloud.yaml`, `config/prompts.yaml`.

---

## 6. Behaviour changes and migration

1. **CLI flags changed.** `--youtube`, `--analyze`, `--research-dir` and `--max-results` are gone. Research uses `--channel` / `--channels-file`; production of a specific idea uses `--produce N`.
2. **Research always starts from reference channels.** The configured niche no longer drives searches.
3. **Intelligence runs whenever `ANTHROPIC_API_KEY` is set.**
4. **Outputs moved** from `outputs/*.json` to `outputs/runs/<run id>/` and `outputs/latest/`. Anything that read `outputs/research.json` should read `outputs/latest/research.json`.
5. **Persistent state moved to `data/`** (git-ignored): `channel_memory.json`, `published.json`, `analytics.json`.
6. **`opportunities.json` changed shape:** it now includes `score`, `tier`, `evidence_count`, `opportunity_id` and `history`, and validated opportunities come first.
7. **Scores are lower for thinly evidenced ideas** (the evidence factor), so absolute numbers aren't comparable with older runs.
8. **Runs fail loudly** when `YOUTUBE_API_KEY` is missing, no channel can be collected, or the YouTube quota is exhausted.
9. **`--learn` now fails with a message** when `YOUTUBE_ACCESS_TOKEN` is missing, instead of silently producing empty memory.
10. **Default model is `claude-opus-5-5`** at `medium` effort; set `CLAUDE_MODEL=claude-sonnet-5-5` to halve the cost.
11. **Python 3.10 or newer** is required (`anthropic` 1.x).
12. **The dashboard needs `Content-Type: application/json`** on POSTs; the bundled `app.js` already sends it.

---

## 7. Remaining limitations and suggestions

None of the 50 findings is open. These are limits of the current implementation and natural next steps, in priority order:

1. **Run one live pipeline** with real keys ([section 8](#8-how-to-verify-on-your-machine)). It's the only way to confirm the Anthropic, YouTube and Analytics calls end to end.
2. **OAuth for analytics.** `--learn` expects a ready-made `YOUTUBE_ACCESS_TOKEN`, and those expire after about an hour. A small OAuth flow that stores a refresh token in `data/` would make learning hands-off.
3. **Automate CTR.** `--ctr-csv` is manual. Creating a Reporting API job for the `channel_reach_basic_a1` report and downloading it on a schedule would remove the export step. The reach-report CTR unit (ratio vs percent) is detected heuristically; check it against your first report.
4. **Per-opportunity production folders.** Producing a second idea from the same run replaces the first one's files (the run folder keeps one production at a time). If you often produce several ideas per run, write each to `runs/<id>/produced/<opportunity_id>/`.
5. **Watch prompt cost with `--transcripts`.** Excerpts add up to ~25k input tokens to the intelligence call. Prompt caching won't help much because the research changes every run; lower `CLAUDE_EFFORT` or use Sonnet if cost matters.
6. **Roadmap items** from the README remain out of scope: Reddit/search adapters, breakout detection, voice and video rendering, YouTube upload and scheduling, RPM and affiliate learning.

---

## 8. How to verify on your machine

From the repository root (Python 3.10+):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest -q
```

Expected: `130 passed`. No network access or keys needed.

Then one live run with `YOUTUBE_API_KEY` and `ANTHROPIC_API_KEY` in `.env`:

```powershell
.venv\Scripts\python main.py --prompt "A calm documentary on why Japanese trains are never late" --format documentary
.venv\Scripts\python main.py --produce 1
```

For a prompt run, also check that `outputs/latest/intent.json` has sensible `search_queries` and that the brief follows the requested format.

Check in `outputs/latest/`:

- `research_territory.json` has a real label and a confidence other than `unrated`.
- `intelligence.json` has `insights` with `gap_candidates` objects and no `error` key.
- `opportunities.json` has at least one `"tier": "validated"` entry with a non-empty `angle`.
- `video_brief.json` and `script.json` have no `fallback_reason`, and the script has `sections`.
- `qa_report.json` lists claims to verify.

Then the dashboard: `.\scripts\start_dashboard.ps1`, open `http://localhost:3000`, research a channel, and press → on an opportunity. The steps should tick through to Production and the video workspace should fill in.

For learning, after publishing and recording a video:

```powershell
.venv\Scripts\python main.py --learn --analytics-start 2026-09-01 --analytics-end 2026-09-30 --ctr-csv "Table data.csv"
```

---

## 9. Pass 3: prompt input and dashboard redesign

### 9.1 Prompt input

**Why:** reference channels answer "what's working in this space?". A creator who already knows what they want to make needs a different question answered: "what's the best angle for *this* video, and how should it be made?". A prompt covers that, and combining both ("my idea, informed by these channels") is the strongest input.

**How it works:**

1. **Understand the prompt.** New `src/intent.py:IntentAgent` turns the free text into a structured brief (`intent.json`): topic, summary, format, target length, tone, audience, must-include and avoid lists, and 3–5 YouTube search queries. Format and length picked in the dashboard (or `--format` / `--length`) override what the model reads from the text. Without an Anthropic key, the first sentence of the prompt becomes the topic and the only search query.
2. **Search the topic.** `ResearchAgent.collect_queries` runs the queries and interleaves results across them, so the first query can't crowd out the others (about 100 quota units per query).
3. **Anchor the territory.** Territory inference keeps the label on your topic and uses the evidence only for sub-territories, audience and confidence. If reference channels are added, their videos join the evidence; if they all fail, the run continues on topic search.
4. **Propose angles.** The analyst is told what the creator wants and asked for gap candidates that are specific angles for that video, in that format.
5. **Produce to spec.** The brief and script prompts put the creator's request first (it overrides the channel's default format and tone), and QA checks the script length against the requested length.

**Design decisions:**

- A prompt run still produces a ranked list of angles instead of jumping straight to a script. You keep the choice, and every angle shows its evidence.
- A prompt run skips the separate "wider YouTube validation" search, because the topic search already is wider-YouTube evidence. This saves about 300 quota units.
- A prompt that finds no videos stops the run with a clear message instead of falling back to config-seed ideas.

**Interfaces:** `PipelineOptions(prompt=..., video_format=..., video_length=...)`; CLI `--prompt`, `--format {explainer,tutorial,documentary,list,commentary,review,short}`, `--length {short,5-8,8-15,15+}`; `POST /api/run` accepts `prompt`, `format`, `length` and `channels` (at least one of prompt or channels; prompts up to 2,000 characters).

### 9.2 Dashboard redesign

The old dashboard was one long page whose sidebar links pointed at the same few panels, with 8–10px text in many places and no light theme. The new one:

- **Four linkable views:** New video, Opportunities, Production and Learning (`#/new`, `#/opportunities`, `#/production`, `#/learning`), so the browser back button and bookmarks work. Phones get a bottom navigation bar instead of the sidebar.
- **A progress bar on every view:** status, a plain-language title (for example "Researching 'Japanese train punctuality'"), and a stepper for either the research steps or the production steps.
- **New video:** a composer with the idea box (character counter, example prompts, Ctrl+Enter to submit), format and length choices, optional reference channels, a hint explaining what will happen with the inputs given, and errors shown next to the form. The side panel shows how Overseer read the brief, what it searched, the topic landscape, the evidence and any warnings.
- **Opportunities:** cards with the score, a "Validated" or "Hypothesis" badge (icon and text, not colour alone), channel-history badge, the angle, labelled meters for demand / audience fit / gap / intent, an evidence-and-scoring panel, and a Produce button. A filter switches between all, validated and hypotheses.
- **Production:** the working title and review status, brief (promise, hook, outline, alternative titles, call to action), script sections, thumbnail concepts, QA checklist with each claim's verification state, and next-step commands with copy buttons. Fallback output is flagged.
- **Learning:** headline numbers, top videos, and what Overseer learned (topics, title patterns, video length), each with a useful empty state.

**Accessibility and quality rules applied** (from the UI/UX skill's built-in priority table; its searchable design database wasn't installed on this machine, so no database recommendations were used):

- Semantic color tokens with dark and light themes. The theme follows the system setting, can be toggled, and is remembered.
- WCAG AA contrast for all text (measured), 16px body text, nothing under 12px.
- Tap targets of 44px for primary controls.
- Visible focus rings, a skip link, real `<button>`/`<a>`/`<fieldset>` elements, labels on every input, and screen-reader text for step status.
- SVG icons instead of emoji or text glyphs, and `prefers-reduced-motion` support.
- Polling re-renders a region only when its data changes, so open panels and keyboard focus survive the 2-second refresh.
- No external fonts, scripts or CDNs: the dashboard keeps working offline.

**Bug found while verifying:** clicking an example prompt didn't clear an earlier "describe your video" error, because filling the box from code fires no input event. Fixed.

### 9.3 Server support

- `/api/status` now includes `intent`, the configured `channel` name, a detailed `production` object (brief, script sections, thumbnails, QA checks and claims, run folder) and richer `memory` / `analytics` (top topics, title patterns, length buckets, top videos).
- After a restart the server also restores the last run's intent.

### 9.4 Files

| File | Change |
|---|---|
| `src/intent.py` | **New:** `IntentAgent`, format and length choices |
| `src/research.py` | `collect_queries` with interleaved results; `collect_youtube` now uses it |
| `src/intelligence.py` | `infer_territory(focus=...)`, `analyze(intent=...)` |
| `src/prompting.py` | Creator's request first; `target_minutes()` |
| `src/brief.py`, `src/script.py`, `src/qa.py` | Take the intent; QA uses the requested length |
| `src/pipeline.py` | Prompt, format and length options; topic search; intent saved and reloaded for production |
| `src/output.py` | Run summary shows the prompt |
| `main.py` | `--prompt`, `--format`, `--length` |
| `overseer_server.py` | Prompt fields on `/api/run`, detailed production and learning state |
| `web/index.html`, `web/styles.css`, `web/app.js` | Rewritten |
| `tests/test_intent.py` | **New:** 10 tests for prompt parsing, prompt runs, combined runs and production |
| `tests/fakes.py`, `tests/test_server.py`, `tests/test_main.py` | 13 more tests: prompt requests and validation for the server and CLI |

### 9.5 Not verified

- **How well Claude turns real prompts into search queries.** Tests use scripted answers. Check `intent.json` after your first real prompt run.
- **The redesigned dashboard against a live server.** It was checked against mock data served statically, so the POST paths were exercised only up to the server's response.
