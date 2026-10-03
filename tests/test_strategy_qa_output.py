from fakes import make_opportunity

from src.output import RUN_FILE, RunWriter, load_json
from src.qa import QAAgent, unresolved_claims
from src.strategy import StrategyAgent


def test_pillars_follow_research_territory(config):
    territory = {"label": "Bread baking", "sub_territories": ["Sourdough", "Enriched doughs"]}
    opportunities = [
        make_opportunity(topic="Sourdough starter basics"),
        make_opportunity(topic="Brioche at home", angle="Enriched doughs without a mixer"),
    ]

    plan = StrategyAgent(config).build(opportunities, territory)

    assert [p["name"] for p in plan.pillars] == ["Sourdough", "Enriched doughs"]
    assert plan.pillars[0]["topics"] == ["Sourdough starter basics"]
    assert plan.pillars[1]["topics"] == ["Brioche at home"]
    assert plan.pillars[0]["source"] == "research territory"
    assert plan.backlog[0]["tier"] == "validated"


def test_pillars_fall_back_to_config(config):
    plan = StrategyAgent(config).build([make_opportunity(topic="Quick dinners for two")], {})

    assert [p["name"] for p in plan.pillars] == ["Quick dinners", "Meal prep"]
    assert plan.pillars[0]["topics"] == ["Quick dinners for two"]


def test_qa_collects_claims_and_checks(config):
    brief = {"working_title": "Bread", "opening_hook": "Hook", "claims_to_verify": ["Yeast doubles in 1h"]}
    script = {
        "estimated_minutes": 30,
        "sections": [{"heading": "a", "narration": ""}],
        "fact_check_queue": ["Yeast doubles in 1h", "Flour has 10% protein"],
    }
    thumbnail = {"concepts": [{"text": "THIS IS WAY TOO MANY WORDS"}]}

    report = QAAgent(config).review(brief, script, thumbnail)

    assert [c["claim"] for c in report["claims"]] == ["Yeast doubles in 1h", "Flour has 10% protein"]
    assert set(report["failed_checks"]) == {
        "Script has sections with narration",
        "Script length is within 50% of the target",
        "Thumbnail text is 5 words or fewer",
    }
    assert report["publish_ready"] is False


def test_unresolved_claims_need_verified_and_source():
    report = {"claims": [
        {"claim": "a", "verified": True, "source": "https://example.com"},
        {"claim": "b", "verified": True, "source": ""},
        {"claim": "c", "verified": False, "source": "x"},
    ]}
    assert unresolved_claims(report) == ["b", "c"]


def test_run_writer_creates_unique_runs_and_publishes_latest(isolated_environment):
    first = RunWriter.create()
    second = RunWriter.create()
    first.write_json(RUN_FILE, {"run_id": first.run_id})
    first.write_json("opportunities.json", [make_opportunity()])

    assert first.run_dir != second.run_dir
    latest = first.publish_latest()

    assert latest == isolated_environment["outputs"] / "latest"
    saved = load_json(latest / "opportunities.json")
    assert saved[0]["tier"] == "validated" and "score" in saved[0]
    assert RunWriter.open().run_dir == first.run_dir
