import pytest
from fakes import FakeResearcher, OfflineLLM, ScriptedLLM

from src.learning import PerformanceMemory
from src.memory import MemoryStore
from src.output import RUN_FILE, load_json
from src.pipeline import PipelineError, PipelineOptions, produce_from_run, run_pipeline
from src.research import YouTubeQuotaError

EXAMPLE = "https://youtube.com/@example"
BROKEN = "https://youtube.com/@broken"

TERRITORY = {
    "label": "Index fund investing",
    "sub_territories": ["Index funds", "ETFs"],
    "audience": "New investors",
    "confidence": "high",
    "evidence": ["Titles repeatedly cover index funds."],
}
INSIGHTS = {
    "recurring_questions": [], "audience_pain_points": [], "desired_outcomes": [],
    "topic_patterns": [], "hook_patterns": [], "title_patterns": [],
    "content_gaps": [], "evidence_notes": [],
    "gap_candidates": [{
        "topic": "Index fund mistakes",
        "angle": "The five errors new investors make",
        "supporting_item_ids": [1],
        "evidence": "Mistake videos outperform.",
    }],
}


def test_offline_run_writes_a_run_folder_and_latest(config, isolated_environment):
    researcher = FakeResearcher()
    result = run_pipeline(config, PipelineOptions(channels=[EXAMPLE]), llm=OfflineLLM(), researcher=researcher)

    assert len(result.channel_profiles) == 1
    assert len(result.research) == 3
    assert result.territory["confidence"] == "unrated"
    assert researcher.validation_calls == []
    assert result.opportunities
    assert any("ANTHROPIC_API_KEY" in warning for warning in result.warnings)

    assert result.run_dir.parent == isolated_environment["outputs"] / "runs"
    assert (result.run_dir / "research.json").exists()
    latest = isolated_environment["outputs"] / "latest"
    assert load_json(latest / RUN_FILE)["status"] == "completed"
    assert (latest / "run_summary.md").exists()


def test_failed_channel_is_a_warning_when_others_succeed(config):
    result = run_pipeline(
        config,
        PipelineOptions(channels=[BROKEN, EXAMPLE]),
        llm=OfflineLLM(),
        researcher=FakeResearcher(failing={BROKEN}),
    )

    assert len(result.channel_profiles) == 1
    assert any(BROKEN in warning for warning in result.warnings)


def test_run_fails_when_no_channel_can_be_collected(config, isolated_environment):
    with pytest.raises(PipelineError):
        run_pipeline(
            config,
            PipelineOptions(channels=[BROKEN]),
            llm=OfflineLLM(),
            researcher=FakeResearcher(failing={BROKEN}),
        )
    [run_dir] = (isolated_environment["outputs"] / "runs").iterdir()
    assert load_json(run_dir / RUN_FILE)["status"] == "failed"
    assert not (isolated_environment["outputs"] / "latest").exists()


def test_quota_error_stops_the_run(config):
    researcher = FakeResearcher(error=YouTubeQuotaError("quota exhausted"))
    with pytest.raises(PipelineError, match="quota exhausted"):
        run_pipeline(config, PipelineOptions(channels=[EXAMPLE, BROKEN]), llm=OfflineLLM(), researcher=researcher)


def test_run_requires_channels(config):
    with pytest.raises(PipelineError):
        run_pipeline(config, PipelineOptions(channels=[]), llm=OfflineLLM(), researcher=FakeResearcher())


def test_full_run_with_llm_produces_and_runs_qa(config):
    researcher = FakeResearcher()
    llm = ScriptedLLM(
        territory=TERRITORY,
        insights=INSIGHTS,
        brief={"working_title": "Index fund mistakes", "opening_hook": "Hook", "claims_to_verify": ["Fees cost 1%"]},
        script={"title": "t", "estimated_minutes": 8, "sections": [{"heading": "h", "narration": "n", "visual_direction": "chart"}], "fact_check_queue": []},
    )

    result = run_pipeline(
        config,
        PipelineOptions(channels=[EXAMPLE], production=True),
        llm=llm,
        researcher=researcher,
    )

    assert researcher.validation_calls == ["Index fund investing"]
    top = result.opportunities[0]
    assert top.topic == "Index fund mistakes" and top.tier == "validated"
    assert [p["name"] for p in result.strategy.pillars] == ["Index funds", "ETFs"]
    assert result.brief["opportunity_id"] == top.opportunity_id
    assert result.production_plan["scenes"][0]["asset_type"] == "data_visual"
    assert result.qa_report["claims"][0]["claim"] == "Fees cost 1%"
    assert load_json(result.run_dir / RUN_FILE)["produced"]["topic"] == "Index fund mistakes"
    # The brief prompt carries the territory, not the configured niche.
    brief_prompt = next(p for p in llm.prompts if "Create a YouTube video brief" in p)
    assert "Index fund investing" in brief_prompt and "New investors" in brief_prompt


def test_channel_memory_is_attached_to_matching_opportunities(config):
    MemoryStore().save(PerformanceMemory(topic_signals={
        "index fund mistakes": {"mean": 61.0, "min": 55.0, "max": 67.0, "count": 2.0},
    }))
    llm = ScriptedLLM(territory=TERRITORY, insights=INSIGHTS)

    result = run_pipeline(config, PipelineOptions(channels=[EXAMPLE]), llm=llm, researcher=FakeResearcher())

    top = result.opportunities[0]
    assert top.history["retention"]["mean"] == 61.0
    assert "Channel history" in top.evidence[-1]


def test_produce_from_latest_run(config):
    run_pipeline(config, PipelineOptions(channels=[EXAMPLE]), llm=OfflineLLM(), researcher=FakeResearcher())

    result = produce_from_run(config, 1, llm=OfflineLLM())

    assert result.selected.topic == result.opportunities[1].topic
    assert result.brief["fallback_reason"]
    assert (result.run_dir / "qa_report.json").exists()
    assert any("no sections" in warning for warning in result.warnings)


def test_produce_rejects_bad_index(config):
    run_pipeline(config, PipelineOptions(channels=[EXAMPLE]), llm=OfflineLLM(), researcher=FakeResearcher())

    with pytest.raises(PipelineError, match="choose a number"):
        produce_from_run(config, 99, llm=OfflineLLM())


def test_produce_without_any_run(config):
    with pytest.raises(PipelineError, match="No completed run"):
        produce_from_run(config, 0, llm=OfflineLLM())
