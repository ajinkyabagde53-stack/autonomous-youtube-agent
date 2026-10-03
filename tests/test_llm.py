import pytest
from fakes import make_opportunity

from src.brief import VideoBriefAgent
from src.llm import LLMClient, LLMError, LLMUnavailable, parse_json_object


class FailingLLM:
    available = True

    def complete_json(self, system, prompt, schema, max_tokens=0):
        raise LLMError("boom")


class RecordingLLM:
    available = True

    def __init__(self, response):
        self.response = response
        self.prompts = []

    def complete_json(self, system, prompt, schema, max_tokens=0):
        self.prompts.append(prompt)
        return self.response


def test_parse_plain_json():
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_strips_code_fence():
    assert parse_json_object('```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}


def test_parse_ignores_surrounding_prose():
    assert parse_json_object('Here you go:\n{"a": 1}\nThanks') == {"a": 1}


@pytest.mark.parametrize("text", ["not json", "[1, 2]", '{"a": '])
def test_parse_rejects_non_objects(text):
    with pytest.raises(LLMError):
        parse_json_object(text)


def test_client_without_key_raises_unavailable():
    client = LLMClient()

    assert not client.available
    with pytest.raises(LLMUnavailable):
        client.complete_json("system", "prompt", {"type": "object"})


def test_empty_env_values_use_defaults(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "")
    monkeypatch.setenv("CLAUDE_EFFORT", "")

    client = LLMClient()

    assert client.model == "claude-opus-5-5"
    assert client.effort == "medium"


def test_brief_falls_back_with_reason(config):
    brief = VideoBriefAgent(config, FailingLLM()).create(make_opportunity())

    assert brief["working_title"] == "index fund basics"
    assert brief["fallback_reason"] == "boom"


def test_brief_prompt_uses_research_territory(config):
    llm = RecordingLLM({"working_title": "x"})
    territory = {
        "label": "Personal finance",
        "sub_territories": ["index funds"],
        "audience": "First-time investors in their 20s",
        "confidence": "high",
        "evidence": [],
    }

    VideoBriefAgent(config, llm).create(make_opportunity(), {}, territory)

    prompt = llm.prompts[0]
    assert "Personal finance" in prompt
    assert "First-time investors in their 20s" in prompt
    assert "voice and format only" in prompt
