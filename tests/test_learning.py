import pytest
from fakes import make_opportunity

from src.analytics import VideoPerformance
from src.learning import LearningAgent, PerformanceMemory
from src.memory import MemoryStore, PublishedRegistry, parse_video_id


def test_learning_memory_aggregates_topic_retention():
    videos = [
        VideoPerformance(video_id="1", title="How to automate reports", average_percentage_viewed=42.0, ctr=4.2),
        VideoPerformance(video_id="2", title="How to automate workflows", average_percentage_viewed=58.0, ctr=5.0),
    ]
    opportunities = {
        "1": make_opportunity(topic="automation"),
        "2": "automation",  # the published registry stores plain topics
    }

    memory = LearningAgent().build_memory(videos, opportunities)

    assert memory.topic_signals["automation"]["mean"] == 50.0
    assert memory.topic_signals["automation"]["count"] == 2.0
    assert memory.title_metric == "ctr"
    assert memory.title_signals["how-to"]["mean"] == 4.6


def test_title_signals_fall_back_to_views_and_explain_why():
    videos = [VideoPerformance(video_id="1", title="Why bread rises", views=900)]

    memory = LearningAgent().build_memory(videos)

    assert memory.title_metric == "views"
    assert memory.title_signals["why"]["mean"] == 900.0
    assert any("--ctr-csv" in note for note in memory.notes)
    assert any("--record-published" in note for note in memory.notes)


def test_videos_without_titles_are_left_out_of_title_signals():
    videos = [VideoPerformance(video_id="dQw4w9WgXcQ", title="", views=10)]

    memory = LearningAgent().build_memory(videos)

    assert memory.title_signals == {}
    assert any("no title" in note for note in memory.notes)


def test_format_signals_bucket_by_length():
    videos = [
        VideoPerformance(video_id="a", title="x", duration_seconds=45, average_percentage_viewed=80.0),
        VideoPerformance(video_id="b", title="y", duration_seconds=600, average_percentage_viewed=40.0),
        VideoPerformance(video_id="c", title="z", duration_seconds=700, average_percentage_viewed=50.0),
    ]

    memory = LearningAgent().build_memory(videos)

    assert memory.format_signals["short (60s or less)"]["mean"] == 80.0
    assert memory.format_signals["8-20 min"]["mean"] == 45.0


@pytest.mark.parametrize("title,pattern", [
    ("How to bake bread", "how-to"),
    ("Why sourdough fails", "why"),
    ("Best pans of 2026", "best"),
    ("Cast iron vs steel", "comparison"),
    ("Is butter bad?", "question"),
    ("7 knife skills", "number-led"),
    ("Weeknight dinner", "general"),
])
def test_title_patterns(title, pattern):
    assert LearningAgent._title_pattern(title) == pattern


def test_history_attaches_to_similar_topics_without_changing_score():
    memory = PerformanceMemory(topic_signals={
        "sourdough starter basics": {"mean": 55.0, "min": 50.0, "max": 60.0, "count": 2.0},
    })
    similar = make_opportunity(topic="Sourdough starter basics for beginners")
    unrelated = make_opportunity(topic="Cast iron care")

    adjusted = LearningAgent().apply_to_opportunities([similar, unrelated], memory)

    assert adjusted[0].history["matched_topic"] == "sourdough starter basics"
    assert adjusted[0].score == similar.score
    assert "Channel history" in adjusted[0].evidence[-1]
    assert adjusted[1].history == {}


def test_memory_store_round_trip(isolated_environment):
    memory = PerformanceMemory(title_metric="ctr", videos_analyzed=3, notes=["n"])
    store = MemoryStore()

    store.save(memory)

    assert store.path == isolated_environment["data"] / "channel_memory.json"
    assert store.load() == memory


def test_memory_store_ignores_unknown_keys(isolated_environment):
    path = isolated_environment["data"] / "channel_memory.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"topic_signals": {}, "legacy_field": 1}', encoding="utf-8")

    assert MemoryStore().load() == PerformanceMemory()


@pytest.mark.parametrize("value", [
    "dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10",
    "https://youtu.be/dQw4w9WgXcQ",
    "youtube.com/shorts/dQw4w9WgXcQ",
])
def test_parse_video_id(value):
    assert parse_video_id(value) == "dQw4w9WgXcQ"


def test_parse_video_id_rejects_garbage():
    with pytest.raises(ValueError):
        parse_video_id("https://example.com/watch?v=nope")


def test_published_registry_replaces_entries_per_video():
    registry = PublishedRegistry()
    registry.record("dQw4w9WgXcQ", "opp1", "topic one", "Title", "run1")
    registry.record("dQw4w9WgXcQ", "opp2", "topic two", "Title", "run2")

    assert registry.topic_by_video() == {"dQw4w9WgXcQ": "topic two"}
