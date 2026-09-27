from __future__ import annotations

import json

from .llm import LLMClient
from .models import ChannelConfig, ResearchItem


class IntelligenceAgent:
    """Convert raw research into structured, evidence-first intelligence."""

    def __init__(self, config: ChannelConfig, llm: LLMClient | None = None) -> None:
        self.config = config
        self.llm = llm or LLMClient()

    def infer_territory(
        self,
        reference_profiles: list[dict],
        items: list[ResearchItem],
    ) -> dict:
        """Infer the research territory from the channels the user selected.

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
            return {
                "label": "Unknown",
                "sub_territories": [],
                "audience": "",
                "confidence": "unrated",
                "evidence": ["No reference-channel evidence was collected."],
            }

        prompt = f"""
You are the territory-classification layer of a YouTube research system.

The user selected reference YouTube channels to define what Overseer should
study. Infer the research territory ONLY from the supplied channel metadata,
channel descriptions, recurring video titles/descriptions, YouTube topic
metadata, and observed performance patterns.

Do NOT use the user's own channel niche, audience, monetization settings, or
any outside assumption to decide the territory.

Return valid JSON with exactly these keys:
- label: one concise territory label, broad enough to cover all supplied
  channels but specific enough to guide wider YouTube validation.
- sub_territories: 3-6 concise sub-territories actually evidenced by the data.
- audience: a concise description of the audience evidenced by the channels.
- confidence: exactly one of "high", "medium", or "low".
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

        result = self.llm.complete_json(
            "You are an evidence-first YouTube research territory classifier.",
            prompt,
        )

        if not isinstance(result, dict):
            return {
                "label": "Reference-channel territory",
                "sub_territories": [],
                "audience": "",
                "confidence": "low",
                "evidence": ["Territory inference returned an invalid structure."],
            }

        return {
            "label": str(result.get("label", "Reference-channel territory")).strip()
            or "Reference-channel territory",
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
    ) -> dict:
        compact = [
            {
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
            for item in items[:60]
        ]

        if not compact:
            return {"items_analyzed": 0, "insights": {}}

        territory_label = (territory or {}).get("label", "reference-channel territory")
        territory_subs = (territory or {}).get("sub_territories", [])
        territory_audience = (territory or {}).get("audience", "")

        prompt = f"""
Research territory: {territory_label}
Sub-territories: {json.dumps(territory_subs, ensure_ascii=False)}
Observed audience: {territory_audience}

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

Each should be an array. Do not invent metrics or facts. If evidence is weak,
say so. Keep the analysis grounded in the supplied channels and videos.

For gap_candidates, return up to 8 specific video-topic opportunities. A useful
candidate should have evidence of audience demand or attention AND some
indication that the reference-channel landscape is incomplete, fragmented, or
saturated in a way that leaves room for a differentiated treatment. A gap alone
is not enough. Include the observed evidence in evidence_notes rather than
pretending the candidate is guaranteed to perform.

Do not use the configured channel niche or audience to bias the analysis.

RESEARCH:
{json.dumps(compact, ensure_ascii=False)}
"""

        result = self.llm.complete_json(
            "You are an evidence-first YouTube audience and content intelligence analyst.",
            prompt,
        )

        return {
            "items_analyzed": len(items),
            "research_territory": territory or {},
            "insights": result,
        }
