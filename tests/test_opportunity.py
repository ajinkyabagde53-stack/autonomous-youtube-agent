from src.config import load_channel_config
from src.models import ResearchItem
from src.opportunity import OpportunityEngine


def test_seed_opportunities_exist():
    config = load_channel_config()
    opportunities = OpportunityEngine(config).generate([])

    assert opportunities
    assert all(0 <= item.score <= 1 for item in opportunities)


def test_research_signals_change_opportunity():
    config = load_channel_config()
    research = [
        ResearchItem(
            source="youtube",
            title="High interest example",
            topics=["test topic"],
            metadata={
                "view_count": 100000,
                "like_count": 5000,
                "comment_count": 500,
            },
        ),
        ResearchItem(
            source="youtube",
            title="Second example",
            topics=["test topic"],
            metadata={
                "view_count": 50000,
                "like_count": 1500,
                "comment_count": 100,
            },
        ),
    ]

    opportunities = OpportunityEngine(config).generate(research)

    assert len(opportunities) == 1
    assert opportunities[0].topic == "test topic"
    assert 0 <= opportunities[0].score <= 1
    assert opportunities[0].evidence
