import pytest
from fakes import FakeResearcher, OfflineLLM, ScriptedLLM, make_opportunity

from src.brief import VideoBriefAgent
from src.intent import IntentAgent
from src.output import RUN_FILE, load_json
from src.pipeline import PipelineError, PipelineOptions, produce_from_run, run_pipeline
from src.prompting import target_minutes

PROMPT = "A calm documentary about why Japanese trains are never late. Include the 1964 Shinkansen. No stock footage clichés."
INTENT = {
    "topic": "Japanese train punctuality",
    "summary": "A calm documentary on why Japan's trains run on time.",
    "video_format": "documentary",
    "target_minutes": 0,
    "tone": "calm",
    "audience": "curious general viewers",
    "must_include": ["1964 Shinkansen"],
    "avoid": ["stock footage clichés"],
    "search_queries": ["japanese trains on time", "Japanese train punctuality", "shinkansen history"],
}


def test_parse_cleans_queries_and_applies_choices():
    intent = IntentAgent(ScriptedLLM(intent=INTENT)).parse(PROMPT, video_format="explainer", video_length="8-15")

    assert intent["topic"] == "Japanese train punctuality"
    # Topic first, duplicates removed, lower-cased for search.
    assert intent["search_queries"] == [
        "japanese train punctuality",
        "japanese trains on time",
        "shinkansen history",
    ]
    assert intent["video_format"] == "explainer"  # the explicit choice wins
    assert intent["target_minutes"] == 12
    assert intent["must_include"] == ["1964 Shinkansen"]
    assert "error" not in intent


def test_parse_ignores_unknown_choices():
    intent = IntentAgent(ScriptedLLM(intent=INTENT)).parse(PROMPT, video_format="musical", video_length="forever")

    assert intent["video_format"] == "documentary"
    assert intent["target_minutes"] == 0


def test_parse_without_llm_uses_the_first_sentence():
    intent = IntentAgent(OfflineLLM()).parse(PROMPT, video_length="5-8")

    assert intent["topic"] == "A calm documentary about why Japanese trains are never late"
    assert intent["search_queries"] == [intent["topic"]]
    assert intent["target_minutes"] == 7
    assert intent["error"]


def test_target_minutes_prefers_the_prompt(config):
    assert target_minutes(config, {"target_minutes": 12}) == 12
    assert target_minutes(config, {"target_minutes": 0}) == 8
    assert target_minutes(config, None) == 8


def test_brief_prompt_carries_the_request(config):
    llm = ScriptedLLM(brief={"working_title": "x"})
    territory = {"label": "Japanese train punctuality", "sub_territories": [], "audience": "rail fans"}

    VideoBriefAgent(config, llm).create(make_opportunity(), {}, territory, INTENT)

    prompt = llm.prompts[0]
    assert "The creator's request" in prompt
    assert "documentary" in prompt and "1964 Shinkansen" in prompt
    # The creator's audience wins over the researched one.
    assert "curious general viewers" in prompt


def test_offline_prompt_run_searches_the_topic(config):
    researcher = FakeResearcher()
    result = run_pipeline(config, PipelineOptions(prompt=PROMPT), llm=OfflineLLM(), researcher=researcher)

    [(queries, label, _)] = researcher.search_calls
    assert label == result.intent["topic"]
    assert queries == [result.intent["topic"]]
    assert result.territory["label"] == result.intent["topic"]
    assert researcher.validation_calls == []
    assert len(result.research) == 3
    assert result.research_source == "YouTube search for your topic"
    assert (result.run_dir / "intent.json").exists()


def test_prompt_and_channels_combine_and_tolerate_channel_failures(config):
    researcher = FakeResearcher(failing={"@broken"})
    result = run_pipeline(
        config,
        PipelineOptions(prompt=PROMPT, channels=["@broken", "@example"]),
        llm=OfflineLLM(),
        researcher=researcher,
    )
    assert len(result.research) == 6
    assert result.research_source.startswith("Reference channels + YouTube search")

    only_broken = run_pipeline(
        config,
        PipelineOptions(prompt=PROMPT, channels=["@broken"]),
        llm=OfflineLLM(),
        researcher=FakeResearcher(failing={"@broken"}),
    )
    assert any("@broken" in warning for warning in only_broken.warnings)
    assert len(only_broken.research) == 3


def test_prompt_with_no_results_fails_clearly(config):
    with pytest.raises(PipelineError, match="no videos for this prompt"):
        run_pipeline(
            config,
            PipelineOptions(prompt=PROMPT),
            llm=OfflineLLM(),
            researcher=FakeResearcher(search_titles=[]),
        )


def test_full_prompt_run_uses_intent_everywhere(config):
    llm = ScriptedLLM(
        intent={**INTENT, "target_minutes": 20},
        territory={
            "label": "Japanese train punctuality",
            "sub_territories": ["Shinkansen", "Rail operations"],
            "audience": "rail fans",
            "confidence": "medium",
            "evidence": ["Search results cluster on punctuality."],
        },
        insights={
            "recurring_questions": [], "audience_pain_points": [], "desired_outcomes": [],
            "topic_patterns": [], "hook_patterns": [], "title_patterns": [],
            "content_gaps": [], "evidence_notes": [],
            "gap_candidates": [{
                "topic": "Japanese trains punctuality",
                "angle": "The 1964 decision that made lateness unacceptable",
                "supporting_item_ids": [0, 1],
                "evidence": "Punctuality videos draw the most views.",
            }],
        },
        brief={"working_title": "Never Late", "opening_hook": "Hook", "claims_to_verify": []},
        script={"title": "t", "estimated_minutes": 8, "sections": [{"heading": "h", "narration": "n", "visual_direction": "map"}], "fact_check_queue": []},
    )
    researcher = FakeResearcher()

    result = run_pipeline(config, PipelineOptions(prompt=PROMPT, script=True), llm=llm, researcher=researcher)

    territory_prompt = next(p for p in llm.prompts if "territory-classification" in p)
    assert "The user wants to make a video about: Japanese train punctuality" in territory_prompt
    analysis_prompt = next(p for p in llm.prompts if "Analyze the collected YouTube research" in p)
    assert "specific angles for THIS video" in analysis_prompt
    assert result.opportunities[0].angle.startswith("The 1964 decision")
    # 8 estimated minutes against a requested 20 fails the length check.
    assert "Script length is within 50% of the target" in result.qa_report["failed_checks"]
    assert load_json(result.run_dir / RUN_FILE)["options"]["prompt"] == PROMPT


def test_produce_from_run_reloads_the_intent(config):
    run_pipeline(config, PipelineOptions(prompt=PROMPT), llm=OfflineLLM(), researcher=FakeResearcher())

    result = produce_from_run(config, 0, llm=OfflineLLM())

    assert result.intent["prompt"] == PROMPT
