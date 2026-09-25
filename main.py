from __future__ import annotations

import argparse

from src.config import load_channel_config
from src.opportunity import OpportunityEngine
from src.output import write_json, write_summary
from src.research import ResearchAgent
from src.strategy import StrategyAgent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Autonomous YouTube Agent foundation."
    )
    parser.add_argument("--channel-config", default="config/channel.yaml")
    parser.add_argument("--research-dir", default="research")
    args = parser.parse_args()

    config = load_channel_config(args.channel_config)
    research_agent = ResearchAgent(config, args.research_dir)
    research = research_agent.normalize(research_agent.collect())

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
