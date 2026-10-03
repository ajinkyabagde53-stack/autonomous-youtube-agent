from pathlib import Path

import pytest

import src.output as output
from src.config import load_channel_config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def config():
    return load_channel_config(FIXTURES / "channel.yaml")


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Keep every test away from the real outputs/, data/ and API keys."""
    dirs = {"outputs": tmp_path / "outputs", "data": tmp_path / "data"}
    monkeypatch.setattr(output, "OUTPUT_DIR", dirs["outputs"])
    monkeypatch.setattr(output, "DATA_DIR", dirs["data"])
    for name in ("ANTHROPIC_API_KEY", "YOUTUBE_API_KEY", "YOUTUBE_ACCESS_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    return dirs
