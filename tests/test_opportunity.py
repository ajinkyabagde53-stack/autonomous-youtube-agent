from src.config import load_channel_config
from src.opportunity import OpportunityEngine


def test_seed_opportunities_exist():
    config = load_channel_config()
    opportunities = OpportunityEngine(config).generate([])

    assert opportunities
    assert all(0 <= item.score <= 1 for item in opportunities)
