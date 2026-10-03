import pytest
from fakes import FakeResearcher, OfflineLLM

import main
from src.memory import PublishedRegistry
from src.output import RunWriter
from src.pipeline import PipelineOptions, produce_from_run, run_pipeline


def parse(*argv):
    parser = main.build_parser()
    args = parser.parse_args(list(argv))
    main.validate_args(parser, args, main.read_channels(parser, args))
    return args


@pytest.mark.parametrize("argv", [
    [],
    ["--brief"],
    ["--learn"],
    ["--learn", "--analytics-start", "2026-09-30", "--analytics-end", "2026-09-01"],
    ["--learn", "--analytics-start", "30/09/2026", "--analytics-end", "2026-10-01"],
    ["--analytics-start", "2026-09-01", "--analytics-end", "2026-09-30"],
    ["--channel", "@a", "--run", "20260101-000000"],
    ["--record-published", "dQw4w9WgXcQ", "--channel", "@a"],
    ["--force", "--channel", "@a"],
    ["--produce", "0"],
    ["--channel", "@a", "--max-videos", "0"],
    ["--prompt", "   "],
    ["--prompt", "x" * 2001],
    ["--channel", "@a", "--format", "documentary"],
    ["--prompt", "trains", "--format", "musical"],
    ["--prompt", "trains", "--run", "20260101-000000", "--produce", "1"],
])
def test_invalid_combinations_are_rejected(argv):
    with pytest.raises(SystemExit):
        parse(*argv)


@pytest.mark.parametrize("argv", [
    ["--channel", "@a"],
    ["--prompt", "A calm documentary on Japanese trains", "--format", "documentary", "--length", "8-15"],
    ["--prompt", "trains", "--channel", "@a", "--produce", "1"],
    ["--channel", "@a", "--produce", "2", "--script"],
    ["--produce", "1", "--run", "20260101-000000"],
    ["--record-published", "https://youtu.be/dQw4w9WgXcQ"],
    ["--learn", "--analytics-start", "2026-09-01", "--analytics-end", "2026-09-30"],
])
def test_valid_combinations_are_accepted(argv):
    parse(*argv)


def test_produce_alone_means_everything():
    options = main.production_options(parse("--produce", "1"))
    assert options.brief and options.script and options.production and options.thumbnail


def test_record_published_is_gated_on_qa(config, capsys):
    run_pipeline(config, PipelineOptions(channels=["@a"]), llm=OfflineLLM(), researcher=FakeResearcher())
    produce_from_run(config, 0, llm=OfflineLLM())

    assert main.record_published("dQw4w9WgXcQ", None, force=False) == 1
    assert "Not recorded" in capsys.readouterr().out
    assert PublishedRegistry().load() == []

    assert main.record_published("dQw4w9WgXcQ", None, force=True) == 0
    [entry] = PublishedRegistry().load()
    assert entry["video_id"] == "dQw4w9WgXcQ"
    assert entry["run_id"] == RunWriter.open().run_id


def test_record_published_needs_a_produced_video(config, capsys):
    run_pipeline(config, PipelineOptions(channels=["@a"]), llm=OfflineLLM(), researcher=FakeResearcher())

    assert main.record_published("dQw4w9WgXcQ", None, force=True) == 1
    assert "--produce" in capsys.readouterr().out
