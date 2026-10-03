from __future__ import annotations

import json

from collections import defaultdict

from .llm import STRING, STRING_LIST, LLMClient, LLMError, list_of, object_schema
from .models import ChannelConfig, ResearchItem

FALLBACK_TERRITORY_LABEL = "Reference-channel territory"
ANALYSIS_SAMPLE_SIZE = 60
TRANSCRIPT_EXCERPT_CHARS = 1500

TERRITORY_SCHEMA = object_schema({
    "label": STRING,
    "sub_territories": STRING_LIST,
    "audience": STRING,
    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    "evidence": STRING_LIST,
})

INSIGHT_KEYS = (
    "recurring_questions",
    "audience_pain_points",
    "desired_outcomes",
    "topic_patterns",
    "hook_patterns",
    "title_patterns",
    "content_gaps",
    "evidence_notes",
)
GAP_CANDIDATE_SCHEMA = object_schema({
    "topic": STRING,
    "angle": STRING,
    "supporting_item_ids": list_of({"type": "integer"}),
    "evidence": STRING,
})
INSIGHTS_SCHEMA = object_schema({
    **{key: STRING_LIST for key in INSIGHT_KEYS},
    "gap_candidates": list_of(GAP_CANDIDATE_SCHEMA),
})


def _views(item: ResearchItem) -> int:
    return int(item.metadata.get("view_count", 0) or 0)


def sample_for_analysis(
    items: list[ResearchItem],
    limit: int = ANALYSIS_SAMPLE_SIZE,
) -> list[tuple[int, ResearchItem]]:
    """Pick a balanced sample and keep each item's index in `items`.

    Each source (a reference channel, or wider YouTube validation) contributes
    its most-viewed and most-recent videos in turn, so no single channel or
    arrival order dominates what the analyst sees.
    """
    by_source: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(items):
        by_source[item.source].append(index)

    queues: list[list[int]] = []
    for indices in by_source.values():
        by_views = sorted(indices, key=lambda i: _views(items[i]), reverse=True)
        by_recency = sorted(
            indices,
            key=lambda i: str(items[i].metadata.get("published_at", "")),
            reverse=True,
        )
        ordered: list[int] = []
        for pair in zip(by_views, by_recency):
            for index in pair:
                if index not in ordered:
                    ordered.append(index)
        queues.append(ordered)

    chosen: list[int] = []
    while len(chosen) < limit and any(queues):
        for queue in queues:
            if queue and len(chosen) < limit:
                chosen.append(queue.pop(0))
    return [(index, items[index]) for index in chosen]


def fallback_territory(
    profiles: list[dict],
    items: list[ResearchItem],
    reason: str = "",
) -> dict:
    """Return an honest non-LLM territory state rather than inventing one."""
    titles = [profile.get("title", "") for profile in profiles if profile.get("title")]
    evidence = []
    if titles:
        evidence.append("Reference channels collected: " + ", ".join(titles[:5]) + ".")
    if items:
        evidence.append(
            f"{len(items)} public videos were collected from the reference channels."
        )
    if not evidence:
        evidence.append("No usable reference-channel evidence was collected.")
    territory = {
        "label": FALLBACK_TERRITORY_LABEL,
        "sub_territories": [],
        "audience": "",
        "confidence": "unrated",
        "evidence": evidence,
    }
    if reason:
        evidence.append(f"Territory was not inferred: {reason}")
        territory["error"] = reason
    return territory


class IntelligenceAgent:
    """Convert raw research into structured, evidence-first intelligence."""

    def __init__(self, config: ChannelConfig, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient()

    def infer_territory(
        self,
        reference_profiles: list[dict],
        items: list[ResearchItem],
        focus: str = "",
    ) -> dict:
        """Infer the research territory from the evidence collected.

        Without `focus`, the territory comes from the reference channels the
        user selected. With `focus` (the topic from the user's prompt), the
        label stays anchored on that topic and the evidence defines its
        sub-territories and audience.

        The configured channel niche is deliberately excluded. Overseer may be
        asked to study any territory, including finance, philosophy, history,
        architecture, science, or topics unrelated to the user's own channel.
        """
        profiles = [
            {
                "title": profile.get("title", ""),
                "description": profile.get("description", "")[:1200],
                "subscriber_count": profile.get("subscriber_count", 0),
                "video_count": profile.get("video_count", 0),
                "topic_categories": profile.get("topic_categories", []),
            }
            for profile in reference_profiles[:10]
        ]
        videos = [
            {
                "source": item.source,
                "title": item.title,
                "summary": item.summary[:500],
                "published_at": item.metadata.get("published_at", ""),
                "view_count": item.metadata.get("view_count", 0),
                "topic_categories": item.metadata.get("topic_categories", []),
            }
            for item in items[:80]
        ]

        if not profiles and not videos:
            return fallback_territory([], [])

        if focus:
            brief = f"""The user wants to make a video about: {focus}
The evidence below is YouTube search results for that topic, plus any
reference channels the user selected. Keep the territory centred on the
user's topic; use the evidence only to define its sub-territories, audience
and confidence."""
            label_rule = "one concise territory label for the user's topic, phrased the way viewers search."
        else:
            brief = """The user selected reference YouTube channels to define what Overseer should
study. Infer the research territory ONLY from the supplied channel metadata,
channel descriptions, recurring video titles/descriptions, YouTube topic
metadata, and observed performance patterns."""
            label_rule = (
                "one concise territory label, broad enough to cover all supplied\n"
                "  channels but specific enough to guide wider YouTube validation."
            )

        prompt = f"""
You are the territory-classification layer of a YouTube research system.

{brief}

Do NOT use the user's own channel niche, audience, monetization settings, or
any outside assumption to decide the territory.

Return JSON with:
- label: {label_rule}
- sub_territories: 3-6 concise sub-territories actually evidenced by the data.
- audience: a concise description of the audience evidenced by the channels.
- confidence: "high", "medium", or "low".
- evidence: 3-6 concise evidence statements explaining why the territory was
  inferred. Mention channel/video evidence rather than making unsupported
  claims.

If the channels span adjacent subjects, choose the shared research territory
and use sub-territories to preserve the distinctions. Do not force unrelated
channels into a single narrow niche.

REFERENCE CHANNELS:
{json.dumps(profiles, ensure_ascii=False)}

REFERENCE VIDEOS:
{json.dumps(videos, ensure_ascii=False)}
"""

        try:
            result = self.llm.complete_json(
                "You are an evidence-first YouTube research territory classifier.",
                prompt,
                TERRITORY_SCHEMA,
            )
        except LLMError as exc:
            return fallback_territory(reference_profiles, items, str(exc))

        return {
            "label": str(result.get("label", "")).strip() or FALLBACK_TERRITORY_LABEL,
            "sub_territories": [
                str(value).strip()
                for value in result.get("sub_territories", [])
                if str(value).strip()
            ][:6],
            "audience": str(result.get("audience", "")).strip(),
            "confidence": (
                result.get("confidence")
                if result.get("confidence") in {"high", "medium", "low"}
                else "low"
            ),
            "evidence": [
                str(value).strip()
                for value in result.get("evidence", [])
                if str(value).strip()
            ][:6],
        }

    def analyze(
        self,
        items: list[ResearchItem],
        territory: dict | None = None,
        intent: dict | None = None,
    ) -> dict:
        sample = sample_for_analysis(items)
        compact = []
        for index, item in sample:
            entry = {
                "id": index,
                "source": item.source,
                "title": item.title,
                "summary": item.summary[:1000],
                "topics": item.topics,
                "hooks": item.hooks,
                "metadata": {
                    k: v for k, v in item.metadata.items()
                    if k != "transcript"
                },
            }
            transcript = str(item.metadata.get("transcript", "")).strip()
            if transcript:
                # The opening usually carries the hook and the promise.
                entry["transcript_excerpt"] = transcript[:TRANSCRIPT_EXCERPT_CHARS]
            compact.append(entry)

        if not compact:
            return {"items_analyzed": 0, "insights": {}}

        territory_label = (territory or {}).get("label", "reference-channel territory")
        territory_subs = (territory or {}).get("sub_territories", [])
        territory_audience = (territory or {}).get("audience", "")

        request = ""
        if intent:
            request = f"""
The creator already knows what they want to make:
{json.dumps({key: intent.get(key) for key in ("topic", "summary", "video_format", "target_minutes", "tone", "audience", "must_include", "avoid")}, ensure_ascii=False)}
Make gap_candidates specific angles for THIS video: different ways to approach
the requested topic, in the requested format, that the evidence supports.
"""

        prompt = f"""
Research territory: {territory_label}
Sub-territories: {json.dumps(territory_subs, ensure_ascii=False)}
Observed audience: {territory_audience}
{request}
Analyze the collected YouTube research. Return JSON with:
- recurring_questions
- audience_pain_points
- desired_outcomes
- topic_patterns
- hook_patterns
- title_patterns
- content_gaps
- evidence_notes
- gap_candidates

All keys except gap_candidates are arrays of strings. Do not invent metrics or
facts. If evidence is weak, say so. Keep the analysis grounded in the supplied
channels and videos. Some videos include a transcript_excerpt (the opening of
the video); use it to judge hooks and promises.

gap_candidates: up to 8 specific video-topic opportunities. A useful candidate
has evidence of audience demand or attention AND some indication that the
reference-channel landscape is incomplete, fragmented, or saturated in a way
that leaves room for a differentiated treatment. A gap alone is not enough.
For each candidate return:
- topic: a short topic phrase of a few words
- angle: one sentence on the differentiated treatment
- supporting_item_ids: the "id" values of the research videos that show the
  demand or the gap (empty if none do)
- evidence: one sentence on what those videos show
Do not pretend a candidate is guaranteed to perform.

Do not use the configured channel niche or audience to bias the analysis.

RESEARCH:
{json.dumps(compact, ensure_ascii=False)}
"""

        try:
            result = self.llm.complete_json(
                "You are an evidence-first YouTube audience and content intelligence analyst.",
                prompt,
                INSIGHTS_SCHEMA,
            )
        except LLMError as exc:
            return {
                "items_analyzed": len(compact),
                "items_collected": len(items),
                "research_territory": territory or {},
                "insights": {},
                "error": str(exc),
            }

        return {
            "items_analyzed": len(compact),
            "items_collected": len(items),
            "research_territory": territory or {},
            "insights": result,
        }
