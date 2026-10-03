import json

from fakes import ScriptedLLM, make_item

from src.intelligence import IntelligenceAgent, sample_for_analysis


def test_sample_alternates_sources_and_keeps_indices():
    items = (
        [make_item(f"A{n}", views=n, source="youtube:A", n=n) for n in range(10)]
        + [make_item(f"B{n}", views=n, source="youtube:B", n=10 + n) for n in range(3)]
    )

    sample = sample_for_analysis(items, limit=6)

    sources = [item.source for _, item in sample]
    assert sources[:6] == ["youtube:A", "youtube:B"] * 3
    assert all(items[index] is item for index, item in sample)
    # Each source leads with its most-viewed video.
    assert sample[0][1].title == "A9"


def test_analyze_sends_ids_and_transcript_excerpts(config):
    llm = ScriptedLLM(insights={"gap_candidates": []})
    items = [
        make_item("Bread basics", n=0, transcript="Today we bake. " * 200),
        make_item("Pasta basics", n=1),
    ]

    result = IntelligenceAgent(config, llm).analyze(items, {"label": "Home baking"})

    research = json.loads(llm.prompts[0].split("RESEARCH:\n", 1)[1])
    by_title = {entry["title"]: entry for entry in research}
    assert by_title["Bread basics"]["id"] == 0
    assert len(by_title["Bread basics"]["transcript_excerpt"]) == 1500
    assert "transcript" not in by_title["Bread basics"]["metadata"]
    assert "transcript_excerpt" not in by_title["Pasta basics"]
    assert result["items_analyzed"] == 2
