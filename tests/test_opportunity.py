from fakes import make_item

from src.models import ResearchItem
from src.opportunity import OpportunityEngine, opportunity_id


def test_seed_opportunities_are_hypotheses(config):
    opportunities = OpportunityEngine(config).generate([])

    assert opportunities
    assert all(0 <= item.score <= 1 for item in opportunities)
    assert all(item.tier == "hypothesis" for item in opportunities)


def test_research_signals_change_opportunity(config):
    # The original version of this test asserted that item.topics ("test
    # topic") became an opportunity. The engine has always derived candidates
    # from titles instead, so that assertion could never pass.
    research = [
        ResearchItem(
            source="youtube",
            title="High interest example",
            topics=["test topic"],
            metadata={"view_count": 100000, "like_count": 5000, "comment_count": 500},
        ),
        ResearchItem(
            source="youtube",
            title="Second example",
            topics=["test topic"],
            metadata={"view_count": 50000, "like_count": 1500, "comment_count": 100},
        ),
    ]

    opportunities = OpportunityEngine(config).generate(research)

    assert any(item.topic == "high interest" for item in opportunities)
    assert all(0 <= item.score <= 1 for item in opportunities)
    assert all(item.evidence for item in opportunities)


def test_llm_gap_candidates_use_cited_items_and_angle(config):
    research = [make_item("Sourdough starter guide", n=0), make_item("Weeknight pasta", n=1)]
    intelligence = {"insights": {"gap_candidates": [{
        "topic": "Sourdough for beginners",
        "angle": "A no-jargon first loaf",
        "supporting_item_ids": [0, 99],
        "evidence": "Starter videos get questions in comments.",
    }]}}

    [opportunity] = OpportunityEngine(config).generate(research, intelligence)

    assert opportunity.topic == "Sourdough for beginners"
    assert opportunity.angle == "A no-jargon first loaf"
    assert opportunity.evidence_count == 1
    assert opportunity.evidence[0] == "youtube:UC123: Sourdough starter guide"
    assert any(line.startswith("Analyst note:") for line in opportunity.evidence)


def test_string_and_garbage_gap_candidates_are_handled(config):
    research = [make_item("Sourdough starter guide")]
    intelligence = {"insights": {"gap_candidates": ["sourdough starter", {"angle": "no topic"}, 42]}}

    opportunities = OpportunityEngine(config).generate(research, intelligence)

    assert [item.topic for item in opportunities] == ["sourdough starter"]


def test_unsupported_hypothesis_ranks_below_validated(config):
    research = [
        make_item("Sourdough starter guide", views=500, n=0),
        make_item("Sourdough starter mistakes", views=800, n=1),
    ]
    intelligence = {"insights": {"gap_candidates": [
        {"topic": "Underwater basket weaving", "angle": "", "supporting_item_ids": [], "evidence": ""},
        {"topic": "Sourdough starter", "angle": "", "supporting_item_ids": [], "evidence": ""},
    ]}}

    opportunities = OpportunityEngine(config).generate(research, intelligence)

    assert [item.tier for item in opportunities] == ["validated", "hypothesis"]
    hypothesis = opportunities[1]
    assert hypothesis.topic == "Underwater basket weaving"
    assert hypothesis.competition_gap == 0.5
    assert "hypothesis" in hypothesis.evidence[-1]


def test_stopwords_alone_do_not_match(config):
    research = [make_item("How to make the best pasta")]
    intelligence = {"insights": {"gap_candidates": ["how to choose the best laptop"]}}

    [opportunity] = OpportunityEngine(config).generate(research, intelligence)

    assert opportunity.evidence_count == 0


def test_opportunity_id_is_stable_and_territory_scoped():
    assert opportunity_id("Sourdough", "Baking") == opportunity_id(" sourdough ", "baking")
    assert opportunity_id("Sourdough", "Baking") != opportunity_id("Sourdough", "Finance")


def test_evidence_caps_score():
    from fakes import make_opportunity

    strong = make_opportunity(evidence_count=3)
    thin = make_opportunity(evidence_count=0)

    assert thin.score < strong.score
    assert strong.to_dict()["tier"] == "validated"
    assert thin.to_dict()["score"] == thin.score
