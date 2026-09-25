from pathlib import Path

from src.config import load_channel_config
from src.research import ResearchAgent


def test_research_agent_reads_text_files(tmp_path: Path):
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "example.md").write_text(
        "# Example topic\nSome evidence.",
        encoding="utf-8",
    )

    config = load_channel_config()
    items = ResearchAgent(config, str(research_dir)).collect()

    assert len(items) == 1
    assert items[0].title == "Example topic"
