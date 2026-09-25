from __future__ import annotations

from .config import load_channel_config
from .models import ResearchItem
from .opportunity import OpportunityEngine
from .research import ResearchAgent
from .strategy import StrategyAgent
from .youtube import YouTubeResearchAgent


class YouTubeOrchestrator:
    def __init__(self, channel_config: str = "config/channel.yaml") -> None:
        self.config = load_channel_config(channel_config)

    def research(self, max_results_per_query: int = 10) -> list[ResearchItem]:
        local_agent = ResearchAgent(self.config)
        local_items = local_agent.normalize(local_agent.collect())

        youtube_agent = YouTubeResearchAgent(self.config)
        queries = youtube_agent.build_queries(self.config)
        live_items = youtube_agent.search(queries, max_results_per_query)

        return local_agent.normalize([*local_items, *live_items])

    def plan(self, research: list[ResearchItem]):
        opportunities = OpportunityEngine(self.config).generate(research)
        strategy = StrategyAgent(self.config).build(opportunities)
        return opportunities, strategy
