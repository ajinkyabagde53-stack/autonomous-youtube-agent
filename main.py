from __future__ import annotations

import argparse
import logging
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from src.analytics import AnalyticsAgent
from src.config import load_channel_config
from src.intent import MAX_PROMPT_CHARS, VIDEO_FORMATS, VIDEO_LENGTHS
from src.learning import LearningAgent
from src.memory import MemoryStore, PublishedRegistry, parse_video_id
from src.output import RUN_FILE, RunWriter, now_iso, write_data_json
from src.pipeline import (
    PipelineError,
    PipelineOptions,
    PipelineResult,
    produce_from_run,
    run_pipeline,
)
from src.qa import unresolved_claims
from src.youtube_analytics import AnalyticsError, YouTubeAnalyticsAdapter, apply_ctr, load_ctr_csv

PRODUCTION_FLAGS = ("brief", "script", "production", "thumbnail")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Autonomous YouTube Agent. Reference channels define what to "
            "research; the territory is inferred from them."
        ),
        epilog=(
            "Typical flow: research with --prompt and/or --channel, produce an idea with --produce N, "
            "clear qa_report.json, publish, then --record-published VIDEO_ID and "
            "later --learn to feed results back."
        ),
    )
    research = parser.add_argument_group(
        "research",
        "Start from a prompt, from reference channels, or both. With both, the "
        "prompt sets the topic and the channels add evidence.",
    )
    research.add_argument(
        "--prompt",
        metavar="TEXT",
        help='The video you want to make, e.g. "a calm 10-minute documentary on why Japanese trains run on time".',
    )
    research.add_argument("--format", choices=VIDEO_FORMATS, help="Kind of video (with --prompt).")
    research.add_argument("--length", choices=list(VIDEO_LENGTHS), help="Target length in minutes (with --prompt).")
    research.add_argument(
        "--channel",
        action="append",
        default=[],
        metavar="URL",
        help="Reference YouTube channel (@handle, /channel/, /user/ or /c/ URL). Repeat for several.",
    )
    research.add_argument("--channels-file", metavar="PATH", help="Text file with one channel URL per line.")
    research.add_argument("--channel-config", default="config/channel.yaml")
    research.add_argument("--max-videos", type=int, default=50, help="Recent videos per reference channel (1-500).")
    research.add_argument(
        "--validation-results",
        type=int,
        default=25,
        help="YouTube search results to collect: topic search with --prompt, otherwise territory validation (0-50, 0 disables).",
    )
    research.add_argument("--region", default="US", help="YouTube region code for wider validation.")
    research.add_argument("--local-research", metavar="DIR", help="Also include .md/.txt notes from this folder.")
    research.add_argument("--transcripts", action="store_true", help="Fetch transcripts and use their openings in the analysis.")

    production = parser.add_argument_group("production")
    production.add_argument(
        "--produce",
        type=int,
        metavar="N",
        help="Produce opportunity number N (1 = top). Uses this run's research, or --run / the latest run.",
    )
    production.add_argument("--run", metavar="RUN_ID", help="Run folder under outputs/runs to use with --produce or --record-published.")
    production.add_argument("--brief", action="store_true", help="Generate a brief.")
    production.add_argument("--script", action="store_true", help="Generate a script (implies --brief).")
    production.add_argument("--production", action="store_true", help="Generate a production plan (implies --script).")
    production.add_argument("--thumbnail", action="store_true", help="Generate thumbnail concepts (implies --brief).")

    publishing = parser.add_argument_group("publishing and learning")
    publishing.add_argument(
        "--record-published",
        metavar="VIDEO",
        help="Link a published video (ID or URL) to the run's produced opportunity. Refuses while QA has open items.",
    )
    publishing.add_argument("--force", action="store_true", help="With --record-published: record even with open QA items.")
    publishing.add_argument("--learn", action="store_true", help="Update channel memory from YouTube Analytics.")
    publishing.add_argument("--analytics-start", default=None, help="Analytics start date: YYYY-MM-DD.")
    publishing.add_argument("--analytics-end", default=None, help="Analytics end date: YYYY-MM-DD.")
    publishing.add_argument(
        "--ctr-csv",
        metavar="PATH",
        help="Thumbnail impressions/CTR CSV (YouTube Studio export or Reporting API reach report).",
    )
    return parser


def read_channels(parser: argparse.ArgumentParser, args: argparse.Namespace) -> list[str]:
    channels = [url.strip() for url in args.channel if url.strip()]
    if args.channels_file:
        path = Path(args.channels_file)
        if not path.is_file():
            parser.error(f"--channels-file not found: {path}")
        channels.extend(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    return list(dict.fromkeys(channels))


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace, channels: list[str]) -> None:
    wants_production = any(getattr(args, flag) for flag in PRODUCTION_FLAGS)
    if args.prompt is not None:
        args.prompt = args.prompt.strip()
        if not args.prompt:
            parser.error("--prompt is empty")
        if len(args.prompt) > MAX_PROMPT_CHARS:
            parser.error(f"--prompt is longer than {MAX_PROMPT_CHARS} characters")
    researching = bool(channels or args.prompt)
    if not (researching or args.produce or args.record_published or args.learn):
        parser.error(
            "nothing to do: add --prompt and/or --channel, --produce, "
            "--record-published or --learn"
        )
    if (args.format or args.length) and not args.prompt:
        parser.error("--format and --length describe the video in --prompt")
    if not 1 <= args.max_videos <= 500:
        parser.error("--max-videos must be between 1 and 500")
    if not 0 <= args.validation_results <= 50:
        parser.error("--validation-results must be between 0 and 50")
    if wants_production and not (researching or args.produce):
        parser.error("--brief/--script/--production/--thumbnail need --prompt, --channel or --produce")
    if args.produce is not None and args.produce < 1:
        parser.error("--produce numbers start at 1")
    if args.run and researching:
        parser.error("--run selects a saved run; it can't be combined with new research")
    if args.run and not (args.produce or args.record_published):
        parser.error("--run only applies to --produce or --record-published")
    if args.record_published and (researching or args.produce):
        parser.error("--record-published runs on its own (after you have published the video)")
    if args.force and not args.record_published:
        parser.error("--force only applies to --record-published")

    has_dates = args.analytics_start or args.analytics_end
    if args.learn and not (args.analytics_start and args.analytics_end):
        parser.error("--learn requires both --analytics-start and --analytics-end")
    if (has_dates or args.ctr_csv) and not args.learn:
        parser.error("--analytics-start/--analytics-end/--ctr-csv only apply with --learn")
    if args.ctr_csv and not Path(args.ctr_csv).is_file():
        parser.error(f"--ctr-csv not found: {args.ctr_csv}")
    if args.learn:
        try:
            start = date.fromisoformat(args.analytics_start)
            end = date.fromisoformat(args.analytics_end)
        except ValueError:
            parser.error("analytics dates must use YYYY-MM-DD")
        if start > end:
            parser.error("--analytics-start must be on or before --analytics-end")


def production_options(args: argparse.Namespace) -> PipelineOptions:
    flags = {flag: getattr(args, flag) for flag in PRODUCTION_FLAGS}
    if not any(flags.values()):
        # --produce on its own means "the whole package".
        flags = {flag: True for flag in PRODUCTION_FLAGS}
    return PipelineOptions(**flags)


def print_research(channel_name: str, result: PipelineResult) -> None:
    territory = result.territory
    print(f"Run: {result.run_id}  ({result.run_dir})")
    print(f"Channel: {channel_name}")
    if result.intent:
        intent = result.intent
        style = ", ".join(
            part for part in (
                intent.get("video_format"),
                f"~{intent['target_minutes']:g} min" if intent.get("target_minutes") else "",
                intent.get("tone"),
            ) if part
        )
        print(f"Topic from your prompt: {intent.get('topic')}" + (f" ({style})" if style else ""))
        print(f"Searched: {'; '.join(intent.get('search_queries', []))}")
    print(f"Reference channels collected: {len(result.channel_profiles)}")
    print(f"Territory: {territory.get('label', 'Unknown')} ({territory.get('confidence', 'unrated')} confidence)")
    print(f"Research items: {len(result.research)} ({result.research_source})")
    print(f"Opportunities: {len(result.opportunities)}")
    for index, item in enumerate(result.opportunities[:5], 1):
        print(f"  {index}. [{item.score:.2f} {item.tier}] {item.topic}")


def print_production(result: PipelineResult) -> None:
    if not result.selected:
        return
    qa = result.qa_report
    print(f"Produced: {result.selected.topic}")
    print(f"QA: {len(qa.get('failed_checks', []))} failed check(s), {len(qa.get('claims', []))} claim(s) to verify")
    print(f"Review: {result.run_dir / 'qa_report.json'}")


def run_learning(start: str, end: str, ctr_csv: str | None) -> None:
    videos = YouTubeAnalyticsAdapter().fetch_recent(start, end)
    if ctr_csv:
        matched = apply_ctr(videos, load_ctr_csv(ctr_csv))
        print(f"CTR imported for {matched} of {len(videos)} video(s).")

    memory = LearningAgent().build_memory(
        videos,
        PublishedRegistry().topic_by_video(),
        updated_at=now_iso(),
    )
    MemoryStore().save(memory)
    write_data_json("analytics.json", {
        "start_date": start,
        "end_date": end,
        "fetched_at": now_iso(),
        "summary": AnalyticsAgent().summarize(videos),
        "videos": videos,
    })

    print(f"Learning: {len(videos)} video(s) analysed.")
    print(
        f"Memory: {len(memory.topic_signals)} topic(s), "
        f"{len(memory.title_signals)} title pattern(s) by {memory.title_metric or 'n/a'}, "
        f"{len(memory.format_signals)} length bucket(s)."
    )
    for note in memory.notes:
        print(f"Note: {note}")


def record_published(value: str, run_id: str | None, force: bool) -> int:
    try:
        video_id = parse_video_id(value)
        writer = RunWriter.open(run_id)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        return 1

    produced = (writer.read_json(RUN_FILE, {}) or {}).get("produced")
    if not produced:
        print(f"Error: run {writer.run_id} has no produced video. Use --produce first.")
        return 1

    qa = writer.read_json("qa_report.json", {}) or {}
    blockers = [f"failed check: {name}" for name in qa.get("failed_checks", [])]
    blockers += [f"unverified claim: {claim}" for claim in unresolved_claims(qa)]
    if blockers and not force:
        print(f"Not recorded: QA has {len(blockers)} open item(s) in {writer.path('qa_report.json')}:")
        for blocker in blockers:
            print(f"  - {blocker}")
        print("Resolve them, or pass --force to record anyway.")
        return 1

    brief = writer.read_json("video_brief.json", {}) or {}
    entry = PublishedRegistry().record(
        video_id=video_id,
        opportunity_id=produced.get("opportunity_id", ""),
        topic=produced.get("topic", ""),
        title=brief.get("working_title", ""),
        run_id=writer.run_id,
    )
    print(f"Recorded {video_id} for '{entry['topic']}'. Run --learn after it has some views.")
    return 0


def main() -> int:
    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(levelname)s %(name)s: %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args()
    channels = read_channels(parser, args)
    validate_args(parser, args, channels)

    if args.record_published:
        return record_published(args.record_published, args.run, args.force)

    config = load_channel_config(args.channel_config)
    try:
        run_id = args.run
        if channels or args.prompt:
            research_options = PipelineOptions(
                channels=channels,
                prompt=args.prompt or "",
                video_format=args.format or "",
                video_length=args.length or "",
                max_videos_per_channel=args.max_videos,
                validation_results=args.validation_results,
                region_code=args.region,
                local_research_dir=args.local_research,
                transcripts=args.transcripts,
                # With --produce N the chosen idea is produced below instead of #1.
                **({} if args.produce else {flag: getattr(args, flag) for flag in PRODUCTION_FLAGS}),
            )
            result = run_pipeline(config, research_options)
            print_research(config.name, result)
            print_production(result)
            run_id = result.run_id

        if args.produce:
            produced = produce_from_run(
                config,
                args.produce - 1,
                production_options(args),
                run_id=run_id,
            )
            print_production(produced)
    except PipelineError as exc:
        print(f"Error: {exc}")
        return 1

    if args.learn:
        try:
            run_learning(args.analytics_start, args.analytics_end, args.ctr_csv)
        except AnalyticsError as exc:
            print(f"Error: {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
