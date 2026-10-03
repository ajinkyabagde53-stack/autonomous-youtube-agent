"""Test doubles shared by the test modules."""

from src.llm import LLMError
from src.models import Opportunity, ReferenceChannel, ResearchItem


class OfflineLLM:
    available = False

    def complete_json(self, system, prompt, schema, max_tokens=0):
        raise LLMError("ANTHROPIC_API_KEY is not set.")


class ScriptedLLM:
    """Answers by schema shape; anything without a scripted answer fails."""

    available = True

    def __init__(self, territory=None, insights=None, brief=None, script=None, thumbnail=None, intent=None):
        self.answers = {
            "search_queries": intent,
            "label": territory,
            "gap_candidates": insights,
            "working_title": brief,
            "sections": script,
            "concepts": thumbnail,
        }
        self.prompts = []

    def complete_json(self, system, prompt, schema, max_tokens=0):
        self.prompts.append(prompt)
        for key, answer in self.answers.items():
            if key in schema["properties"]:
                if answer is None:
                    raise LLMError(f"no scripted answer for {key}")
                return answer
        raise LLMError("unexpected schema")


def make_item(title, views=1000, source="youtube:UC123", n=0, **metadata):
    return ResearchItem(
        source=source,
        title=title,
        url=f"https://www.youtube.com/watch?v=vid{n:08d}",
        metadata={
            "video_id": f"vid{n:08d}",
            "view_count": views,
            "like_count": views // 20,
            "comment_count": views // 200,
            **metadata,
        },
    )


def make_opportunity(topic="index fund basics", evidence_count=3, **values):
    defaults = dict(
        angle=f"A clear take on {topic}",
        demand_signal=.5,
        audience_fit=.5,
        competition_gap=.5,
        differentiation=.5,
        business_intent=.5,
        rationale="test",
        evidence=["youtube: Example video"],
        evidence_count=evidence_count,
        opportunity_id="opp123",
    )
    defaults.update(values)
    return Opportunity(topic=topic, **defaults)


class FakeResearcher:
    def __init__(self, failing=(), error=None, titles=None, search_titles=None, search_error=None):
        self.failing = set(failing)
        self.error = error
        self.titles = titles or [
            "Index fund basics for beginners",
            "Index fund mistakes to avoid",
            "Index funds vs ETFs explained",
        ]
        self.search_titles = [
            "Why Japanese trains are never late",
            "Japanese trains punctuality explained",
            "How Shinkansen trains stay on time",
        ] if search_titles is None else search_titles
        self.search_error = search_error
        self.validation_calls = []
        self.search_calls = []

    def collect_queries(self, queries, label, region_code="US", max_results=25):
        self.search_calls.append((list(queries), label, max_results))
        if self.search_error:
            raise self.search_error
        return [
            make_item(title, views=5000 * (n + 1), source="youtube", n=100 + n)
            for n, title in enumerate(self.search_titles)
        ]

    def collect_reference_channel(self, url, max_videos=50, region_code="US"):
        if self.error:
            raise self.error
        if url in self.failing:
            raise ValueError("Could not resolve the channel URL.")
        profile = ReferenceChannel(url=url, channel_id="UC123", title="Example Channel")
        videos = [
            make_item(title, views=1000 * (n + 1), n=n)
            for n, title in enumerate(self.titles)
        ]
        return profile, videos

    def collect_youtube(self, territory, region_code="US", max_results=25):
        self.validation_calls.append(territory)
        return []

    def collect(self):
        return []

    @staticmethod
    def normalize(items):
        return list(items)
