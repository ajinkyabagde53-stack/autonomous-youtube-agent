from __future__ import annotations

import argparse

from src.config import load_channel_config
from src.opportunity import OpportunityEngine
from src.output import write_json, write_summary
from src.research import ResearchAgent
from src.strategy import StrategyAgent
from src.transcripts import TranscriptAgent
from src.youtube import YouTubeResearchAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Autonomous YouTube Agent.")
    parser.add_argument("--channel-config", default="config/channel.yaml")
    parser.add_argument("--research-dir", default="research")
    parser.add_argument("--youtube", action="store_true", help="Use the YouTube Data API when YOUTUBE_API_KEY is set.")
    parser.add_argument("--transcripts", action="store_true", help="Attempt transcript retrieval for YouTube results.")
    parser.add_argument("--max-results", type=int, default=10)
    args = parser.parse_args()

    config = load_channel_config(args.channel_config)

    local_agent = ResearchAgent(config, args.research_dir)
    research = local_agent.normalize(local_agent.collect())

    if args.youtube:
        youtube_agent = YouTubeResearchAgent(config)
        queries = youtube_agent.build_queries(config)
        live_items = youtube_agent.search(queries, args.max_results)
        research = local_agent.normalize([*research, *live_items])

        if args.transcripts:
            research = TranscriptAgent().enrich(research)

    opportunities = OpportunityEngine(config).generate(research)
    strategy = StrategyAgent(config).build(opportunities)

    write_json("research.json", research)
    write_json("opportunities.json", opportunities)
    write_json("strategy.json", strategy)
    summary = write_summary(config.name, len(research), opportunities, strategy)

    print(f"Channel: {config.name}")
    print(f"Research items: {len(research)}")
    print(f"Opportunities: {len(opportunities)}")
    print(f"Top opportunity: {opportunities[0].topic if opportunities else 'None'}")
    print(f"Summary: {summary}")


if __name__ == "__main__":
    main()
