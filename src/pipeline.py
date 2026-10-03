from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from .brief import VideoBriefAgent
from .intelligence import FALLBACK_TERRITORY_LABEL, IntelligenceAgent
from .intent import IntentAgent
from .learning import LearningAgent
from .llm import LLMClient
from .memory import MemoryStore
from .models import ChannelConfig, ContentPlan, Opportunity, ResearchItem
from .opportunity import OpportunityEngine
from .output import RUN_FILE, RunWriter, load_json, now_iso
from .production import ProductionPlanner
from .prompting import target_minutes
from .qa import QAAgent
from .research import ResearchAgent, YouTubeQuotaError
from .script import ScriptAgent
from .strategy import StrategyAgent
from .thumbnail import ThumbnailAgent
from .transcripts import TranscriptAgent

log = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """The run cannot continue, e.g. no reference channel could be collected."""


@dataclass
class PipelineOptions:
    """What to research and produce.

    Research starts from a prompt (the topic and kind of video the creator
    wants), from reference channels, or from both: the prompt sets the topic
    and the channels add evidence about style and audience.
    """

    channels: list[str] = field(default_factory=list)
    prompt: str = ""
    video_format: str = ""
    video_length: str = ""
    max_videos_per_channel: int = 50
    validation_results: int = 25
    region_code: str = "US"
    local_research_dir: str | None = None
    transcripts: bool = False
    brief: bool = False
    script: bool = False
    production: bool = False
    thumbnail: bool = False


@dataclass
class PipelineResult:
    run_id: str = ""
    run_dir: Path | None = None
    intent: dict = field(default_factory=dict)
    channel_profiles: list[dict] = field(default_factory=list)
    territory: dict = field(default_factory=dict)
    research: list[ResearchItem] = field(default_factory=list)
    research_source: str = ""
    intelligence: dict = field(default_factory=dict)
    opportunities: list[Opportunity] = field(default_factory=list)
    strategy: ContentPlan | None = None
    selected: Opportunity | None = None
    brief: dict = field(default_factory=dict)
    script: dict = field(default_factory=dict)
    production_plan: dict = field(default_factory=dict)
    thumbnail: dict = field(default_factory=dict)
    qa_report: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    outputs: list[Path] = field(default_factory=list)


# on_progress(event, step, result), where event is "start" or "done".
ProgressCallback = Callable[[str, str, PipelineResult], None]


class _Run:
    """Shared plumbing for one pipeline invocation."""

    def __init__(
        self,
        writer: RunWriter,
        result: PipelineResult,
        llm: LLMClient,
        on_progress: ProgressCallback | None,
    ) -> None:
        self.writer = writer
        self.result = result
        self.llm = llm
        self.on_progress = on_progress

    def save(self, filename: str, value: Any) -> None:
        self.result.outputs.append(self.writer.write_json(filename, value))

    def warn(self, message: str) -> None:
        self.result.warnings.append(message)
        log.warning(message)

    def fallback(self, step: str, reason: str | None) -> None:
        # A missing key is reported once up front, not once per step.
        if reason and self.llm.available:
            self.warn(f"{step} fell back to non-LLM output: {reason}")

    def notify(self, event: str, step: str) -> None:
        if self.on_progress:
            self.on_progress(event, step, self.result)

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        log.info("step %s: start", name)
        self.notify("start", name)
        yield
        log.info("step %s: done", name)
        self.notify("done", name)

    def update_run_file(self, **values: Any) -> None:
        data = self.writer.read_json(RUN_FILE, {}) or {}
        data.update(values)
        self.writer.write_json(RUN_FILE, data)


def run_pipeline(
    config: ChannelConfig,
    options: PipelineOptions,
    *,
    llm: LLMClient | None = None,
    researcher: ResearchAgent | None = None,
    memory_store: MemoryStore | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Research reference channels, plan opportunities, and optionally produce a video.

    The CLI (main.py) and the dashboard (overseer_server.py) both call this,
    so they share one reference-channel-first flow. Artifacts go to
    outputs/runs/<run id>/ as soon as they exist, so a later failure does not
    lose research that already spent API quota. A completed run is copied to
    outputs/latest/.
    """
    options.prompt = options.prompt.strip()
    if not options.channels and not options.prompt:
        raise PipelineError("Describe the video you want to make, or add a reference YouTube channel.")
    if researcher is None:
        if not os.getenv("YOUTUBE_API_KEY"):
            raise PipelineError(
                "YOUTUBE_API_KEY is not set, so YouTube can't be researched."
            )
        researcher = ResearchAgent(config, options.local_research_dir or "research")

    llm = llm or LLMClient()
    writer = RunWriter.create()
    result = PipelineResult(run_id=writer.run_id, run_dir=writer.run_dir)
    run = _Run(writer, result, llm, on_progress)
    run.update_run_file(
        run_id=writer.run_id,
        status="running",
        started_at=now_iso(),
        options=asdict(options),
    )
    log.info(
        "run %s started (%s, %d channel(s))",
        writer.run_id,
        "prompt" if options.prompt else "no prompt",
        len(options.channels),
    )

    try:
        _research_and_plan(config, options, researcher, memory_store, run)
        if options.brief or options.script or options.production or options.thumbnail:
            if result.opportunities:
                _produce(config, options, run, result.opportunities[0])
            else:
                run.warn("No opportunities were generated, so nothing was produced.")
    except Exception as exc:
        run.update_run_file(status="failed", completed_at=now_iso(), error=str(exc))
        raise

    result.outputs.append(writer.write_summary(
        config.name,
        len(result.research),
        result.opportunities,
        result.strategy,
        result.territory,
        result.warnings,
        result.intent,
    ))
    run.update_run_file(status="completed", completed_at=now_iso(), warnings=result.warnings)
    writer.publish_latest()
    return result


def produce_from_run(
    config: ChannelConfig,
    opportunity_index: int,
    options: PipelineOptions | None = None,
    *,
    run_id: str | None = None,
    llm: LLMClient | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Produce a brief, script, production plan and thumbnails for one opportunity
    of a saved run (the latest completed run when run_id is None).

    `opportunity_index` is 0-based, in the order of opportunities.json.
    Production flags in `options` default to everything.
    """
    options = options or PipelineOptions(brief=True, script=True, production=True, thumbnail=True)
    try:
        writer = RunWriter.open(run_id)
    except FileNotFoundError as exc:
        raise PipelineError(str(exc)) from None

    opportunities = [
        Opportunity.from_dict(item)
        for item in writer.read_json("opportunities.json", []) or []
    ]
    if not 0 <= opportunity_index < len(opportunities):
        raise PipelineError(
            f"Run {writer.run_id} has {len(opportunities)} opportunities; "
            f"choose a number from 1 to {len(opportunities)}."
        )

    result = PipelineResult(
        run_id=writer.run_id,
        run_dir=writer.run_dir,
        intent=writer.read_json("intent.json", {}) or {},
        territory=writer.read_json("research_territory.json", {}) or {},
        intelligence=writer.read_json("intelligence.json", {}) or {},
        opportunities=opportunities,
    )
    run = _Run(writer, result, llm or LLMClient(), on_progress)
    if not run.llm.available:
        run.warn("ANTHROPIC_API_KEY is not set: production steps use non-LLM fallbacks.")

    _produce(config, options, run, opportunities[opportunity_index])

    latest_id = (load_json(writer.run_dir.parent.parent / "latest" / RUN_FILE, {}) or {}).get("run_id")
    if latest_id in (None, writer.run_id):
        writer.publish_latest()
    return result


def _research_and_plan(
    config: ChannelConfig,
    options: PipelineOptions,
    researcher: ResearchAgent,
    memory_store: MemoryStore | None,
    run: _Run,
) -> None:
    result = run.result
    if not run.llm.available:
        run.warn(
            "ANTHROPIC_API_KEY is not set: territory inference, intelligence and "
            "production steps use non-LLM fallbacks."
        )

    # Research. Prompt runs: prompt -> topic search (+ channels) -> territory
    # anchored on the topic. Channel-only runs: channels -> territory ->
    # wider YouTube validation of that territory.
    with run.step("research"):
        if options.prompt:
            result.intent = IntentAgent(run.llm).parse(
                options.prompt,
                options.video_format,
                options.video_length,
            )
            run.fallback("Prompt understanding", result.intent.get("error"))
            run.save("intent.json", result.intent)

        reference_items = (
            _collect_reference_channels(researcher, options, run) if options.channels else []
        )
        topic_items = _search_topic(researcher, options, run) if result.intent else []

        intelligence_agent = IntelligenceAgent(config, run.llm)
        result.territory = intelligence_agent.infer_territory(
            result.channel_profiles,
            [*reference_items, *topic_items],
            focus=result.intent.get("topic", ""),
        )
        if result.intent and result.territory.get("label") == FALLBACK_TERRITORY_LABEL:
            # Without inference the creator's own topic is the best label.
            result.territory = {
                **result.territory,
                "label": result.intent["topic"],
                "audience": result.intent.get("audience", ""),
            }
        run.fallback("Territory inference", result.territory.get("error"))
        run.save("research_territory.json", result.territory)

        # A prompt run's topic search already is the wider-YouTube evidence.
        validation_items = [] if result.intent else _validate_territory(researcher, options, run)
        local_items = researcher.collect() if options.local_research_dir else []
        result.research = researcher.normalize(
            [*reference_items, *topic_items, *validation_items, *local_items]
        )
        if result.intent and not result.research:
            raise PipelineError(
                "YouTube returned no videos for this prompt. Try describing the "
                "topic more broadly, or add a reference channel."
            )
        if options.transcripts:
            TranscriptAgent().enrich(result.research)
        result.research_source = _describe_sources(
            reference_items,
            [*topic_items, *validation_items],
            local_items,
            topic_search=bool(result.intent),
        )
        run.save("research.json", result.research)

    with run.step("intelligence"):
        if result.research:
            result.intelligence = intelligence_agent.analyze(
                result.research,
                result.territory,
                result.intent or None,
            )
            run.fallback("Intelligence analysis", result.intelligence.get("error"))
            run.save("intelligence.json", result.intelligence)

    with run.step("opportunity"):
        if not result.research:
            run.warn(
                "No research items were collected, so opportunities are starter "
                "hypotheses from config/channel.yaml."
            )
        opportunities = OpportunityEngine(config).generate(
            result.research,
            result.intelligence,
            result.territory,
        )
        memory = (memory_store or MemoryStore()).load()
        if memory.topic_signals:
            opportunities = LearningAgent().apply_to_opportunities(opportunities, memory)
        result.opportunities = opportunities
        run.save("opportunities.json", result.opportunities)

    with run.step("strategy"):
        result.strategy = StrategyAgent(config).build(result.opportunities, result.territory)
        run.save("strategy.json", result.strategy)


def _collect_reference_channels(
    researcher: ResearchAgent,
    options: PipelineOptions,
    run: _Run,
) -> list[ResearchItem]:
    items: list[ResearchItem] = []
    failures: list[str] = []

    for url in options.channels:
        try:
            profile, videos = researcher.collect_reference_channel(
                url,
                max_videos=options.max_videos_per_channel,
                region_code=options.region_code,
            )
        except YouTubeQuotaError as exc:
            # Every later call would fail the same way.
            raise PipelineError(str(exc)) from None
        except Exception as exc:
            failures.append(f"Reference channel failed ({url}): {type(exc).__name__}: {exc}")
            continue
        run.result.channel_profiles.append(asdict(profile))
        items.extend(videos)

    for failure in failures:
        run.warn(failure)
    # With a prompt the run can continue on topic search alone.
    if not run.result.channel_profiles and not options.prompt:
        raise PipelineError(
            "No reference channel could be collected. " + " ".join(failures)
        )
    return items


def _search_topic(
    researcher: ResearchAgent,
    options: PipelineOptions,
    run: _Run,
) -> list[ResearchItem]:
    """Search YouTube for the prompt's queries (up to ~500 quota units)."""
    intent = run.result.intent
    if options.validation_results <= 0:
        run.warn("Topic search is disabled (--validation-results 0); only reference channels were used.")
        return []
    try:
        return researcher.collect_queries(
            intent.get("search_queries") or [intent.get("topic", "")],
            label=intent.get("topic", ""),
            region_code=options.region_code,
            max_results=options.validation_results,
        )
    except YouTubeQuotaError as exc:
        raise PipelineError(str(exc)) from None
    except Exception as exc:
        run.warn(f"Topic search failed: {type(exc).__name__}: {exc}")
        return []


def _validate_territory(
    researcher: ResearchAgent,
    options: PipelineOptions,
    run: _Run,
) -> list[ResearchItem]:
    label = run.result.territory.get("label", "")
    if options.validation_results <= 0 or not label or label == FALLBACK_TERRITORY_LABEL:
        return []

    try:
        return researcher.collect_youtube(
            label,
            region_code=options.region_code,
            max_results=options.validation_results,
        )
    except Exception as exc:
        run.warn(f"Wider YouTube validation failed: {type(exc).__name__}: {exc}")
        return []


def _describe_sources(
    reference: list[ResearchItem],
    youtube: list[ResearchItem],
    local: list[ResearchItem],
    topic_search: bool = False,
) -> str:
    parts = []
    if reference:
        parts.append("Reference channels")
    if youtube:
        parts.append("YouTube search for your topic" if topic_search else "wider YouTube validation")
    if local:
        parts.append("local research notes")
    if not parts:
        return "No research collected"
    text = " + ".join(parts)
    return text[0].upper() + text[1:]


def _produce(
    config: ChannelConfig,
    options: PipelineOptions,
    run: _Run,
    selected: Opportunity,
) -> None:
    """Brief -> script -> production plan -> thumbnails -> QA for one opportunity."""
    result = run.result
    result.selected = selected
    # Clear anything an earlier production of this run left behind.
    for filename in (
        "video_brief.json",
        "script.json",
        "production_plan.json",
        "thumbnail_concepts.json",
        "qa_report.json",
    ):
        run.writer.path(filename).unlink(missing_ok=True)

    wants_script = options.script or options.production

    with run.step("brief"):
        result.brief = VideoBriefAgent(config, run.llm).create(
            selected,
            result.intelligence,
            result.territory,
            result.intent or None,
        )
        result.brief["opportunity_id"] = selected.opportunity_id
        run.fallback("Video brief", result.brief.get("fallback_reason"))
        run.save("video_brief.json", result.brief)

    if wants_script:
        with run.step("script"):
            result.script = ScriptAgent(config, run.llm).generate(
                result.brief,
                result.territory,
                result.intent or None,
            )
            run.fallback("Script", result.script.get("fallback_reason"))
            run.save("script.json", result.script)

    if options.production:
        with run.step("production"):
            if result.script.get("sections"):
                result.production_plan = ProductionPlanner().build(result.script)
                run.save("production_plan.json", result.production_plan)
            else:
                run.warn("The script has no sections, so no production plan was built.")

    if options.thumbnail:
        with run.step("thumbnail"):
            result.thumbnail = ThumbnailAgent(config, run.llm).generate(result.brief)
            run.fallback("Thumbnail concepts", result.thumbnail.get("fallback_reason"))
            run.save("thumbnail_concepts.json", result.thumbnail)

    with run.step("qa"):
        result.qa_report = QAAgent(config).review(
            result.brief,
            result.script,
            result.thumbnail,
            target_minutes=target_minutes(config, result.intent),
        )
        run.save("qa_report.json", result.qa_report)

    run.update_run_file(produced={
        "opportunity_id": selected.opportunity_id,
        "topic": selected.topic,
        "produced_at": now_iso(),
    })
