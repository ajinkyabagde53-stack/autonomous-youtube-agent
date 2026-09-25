from __future__ import annotations

import argparse

from src.brief import VideoBriefAgent
from src.config import load_channel_config
from src.analytics import VideoPerformance
from src.intelligence import IntelligenceAgent
from src.learning import LearningAgent
from src.memory import MemoryStore
from src.youtube_analytics import YouTubeAnalyticsAdapter
from src.opportunity import OpportunityEngine
from src.output import write_json, write_summary
from src.production import ProductionPlanner
from src.research import ResearchAgent
from src.script import ScriptAgent
from src.strategy import StrategyAgent
from src.thumbnail import ThumbnailAgent
from src.transcripts import TranscriptAgent
from src.youtube import YouTubeResearchAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Autonomous YouTube Agent.")
    parser.add_argument("--channel-config", default="config/channel.yaml")
    parser.add_argument("--research-dir", default="research")
    parser.add_argument("--youtube", action="store_true", help="Use the YouTube Data API.")
    parser.add_argument("--transcripts", action="store_true", help="Attempt transcript retrieval.")
    parser.add_argument("--analyze", action="store_true", help="Run LLM intelligence analysis.")
    parser.add_argument("--brief", action="store_true", help="Generate a brief for the top opportunity.")
    parser.add_argument("--script", action="store_true", help="Generate a script from the generated brief.")
    parser.add_argument("--production", action="store_true", help="Generate a production plan from the script.")
    parser.add_argument("--thumbnail", action="store_true", help="Generate thumbnail concepts from the brief.")
    parser.add_argument("--learn", action="store_true", help="Build channel memory from supplied performance data.")
    parser.add_argument("--analytics-start", default=None, help="Analytics start date: YYYY-MM-DD.")
    parser.add_argument("--analytics-end", default=None, help="Analytics end date: YYYY-MM-DD.")
    parser.add_argument("--max-results", type=int, default=10)
    args = parser.parse_args()

    config = load_channel_config(args.channel_config)
    local_agent = ResearchAgent(config, args.research_dir)
    research = local_agent.normalize(local_agent.collect())

    if args.youtube:
        youtube_agent = YouTubeResearchAgent(config)
        live_items = youtube_agent.search(
            youtube_agent.build_queries(config),
            args.max_results,
        )
        research = local_agent.normalize([*research, *live_items])

        if args.transcripts:
            research = TranscriptAgent().enrich(research)

    intelligence = {}
    if args.analyze:
        intelligence = IntelligenceAgent(config).analyze(research)
        write_json("intelligence.json", intelligence)

    opportunities = OpportunityEngine(config).generate(
        research,
        intelligence,
    )
    strategy = StrategyAgent(config).build(opportunities)

    write_json("research.json", research)
    write_json("opportunities.json", opportunities)
    write_json("strategy.json", strategy)

    brief = {}
    if (args.brief or args.script or args.production or args.thumbnail) and opportunities:
        brief = VideoBriefAgent(config).create(opportunities[0], intelligence)
        write_json("video_brief.json", brief)

    script = {}
    if (args.script or args.production) and brief:
        script = ScriptAgent(config).generate(brief)
        write_json("script.json", script)

    if args.production and script:
        production_plan = ProductionPlanner().build(script)
        write_json("production_plan.json", production_plan)

    if args.thumbnail and brief:
        thumbnail = ThumbnailAgent(config).generate(brief)
        write_json("thumbnail_concepts.json", thumbnail)

    if args.learn and args.analytics_start and args.analytics_end:
        performance = YouTubeAnalyticsAdapter().fetch_recent(
            args.analytics_start,
            args.analytics_end,
        )
        write_json("analytics.json", performance)

        memory = LearningAgent().build_memory(performance)
        MemoryStore().save(memory)
        write_json("learning_summary.json", memory)

    summary = write_summary(config.name, len(research), opportunities, strategy)

    print(f"Channel: {config.name}")
    print(f"Research items: {len(research)}")
    print(f"Opportunities: {len(opportunities)}")
    print(f"Top opportunity: {opportunities[0].topic if opportunities else 'None'}")
    print(f"Summary: {summary}")


if __name__ == "__main__":
    main()
