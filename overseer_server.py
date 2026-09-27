from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from src.config import load_channel_config
from src.opportunity import OpportunityEngine
from src.output import write_json, write_summary
from src.research import ResearchAgent
from src.strategy import StrategyAgent

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
CONFIG = ROOT / "config" / "channel.yaml"

STATE = {
    "run_id": None,
    "status": "idle",
    "started_at": None,
    "completed_at": None,
    "current_step": None,
    "completed_steps": [],
    "errors": [],
    "research_count": 0,
    "opportunity_count": 0,
    "opportunities": [],
    "channel": "Overseer",
    "research_mode": "channel_intelligence",
    "reference_channels": [],
    "channel_profiles": [],
    "research_territory": None,
    "research_source": "",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def public_opportunity(item):
    return {
        "topic": item.topic,
        "angle": item.angle,
        "score": round(item.score * 100),
        "demand": round(item.demand_signal * 100),
        "audience_fit": round(item.audience_fit * 100),
        "competition_gap": round(item.competition_gap * 100),
        "differentiation": round(item.differentiation * 100),
        "business_intent": round(item.business_intent * 100),
        "rationale": item.rationale,
        "evidence": item.evidence,
    }


def _fallback_territory(reference_profiles, reference_research):
    """Return an honest non-LLM territory state rather than inventing one."""
    titles = [profile.title for profile in reference_profiles if profile.title]
    evidence = []
    if titles:
        evidence.append("Reference channels collected: " + ", ".join(titles[:5]) + ".")
    if reference_research:
        evidence.append(
            f"{len(reference_research)} public videos were collected from the "
            "reference channels."
        )
    if not evidence:
        evidence.append("No usable reference-channel evidence was collected.")

    return {
        "label": "Reference-channel territory",
        "sub_territories": [],
        "audience": "",
        "confidence": "unrated",
        "evidence": evidence,
    }


def run_overseer(
    run_id,
    research_mode="channel_intelligence",
    channel_urls=None,
):
    STATE.update(
        run_id=run_id,
        status="running",
        started_at=now(),
        completed_at=None,
        current_step="research",
        research_mode=research_mode,
        completed_steps=[],
        errors=[],
        research_count=0,
        opportunity_count=0,
        opportunities=[],
        reference_channels=channel_urls or [],
        channel_profiles=[],
        research_territory=None,
        research_source="",
    )

    try:
        config = load_channel_config(str(CONFIG))
        research_agent = ResearchAgent(config, "research")

        # Reference channels are the research brief. The user's own configured
        # channel niche is deliberately not used to select or constrain the
        # research territory.
        reference_profiles = []
        reference_research = []

        for channel_url in (channel_urls or []):
            try:
                profile, videos = research_agent.collect_reference_channel(channel_url)
                reference_profiles.append(profile)
                reference_research.extend(videos)
            except Exception as exc:
                STATE["errors"].append(
                    f"Reference channel failed ({channel_url}): "
                    f"{type(exc).__name__}: {exc}"
                )

        STATE["channel_profiles"] = [
            {
                "url": profile.url,
                "channel_id": profile.channel_id,
                "title": profile.title,
                "description": profile.description,
                "subscriber_count": profile.subscriber_count,
                "video_count": profile.video_count,
                "view_count": profile.view_count,
                "country": profile.country,
                "topic_categories": profile.topic_categories,
            }
            for profile in reference_profiles
        ]

        # Infer territory only after channel evidence exists.
        STATE["current_step"] = "intelligence"
        territory = _fallback_territory(reference_profiles, reference_research)

        if reference_profiles and os.getenv("ANTHROPIC_API_KEY"):
            from src.intelligence import IntelligenceAgent

            intelligence_agent = IntelligenceAgent(config)
            territory = intelligence_agent.infer_territory(
                STATE["channel_profiles"],
                reference_research,
            )

        STATE["research_territory"] = territory
        write_json("research_territory.json", territory)

        # Wider YouTube validation happens only after territory inference.
        live_research = []
        if (
            reference_profiles
            and territory.get("label")
            and territory.get("label") != "Reference-channel territory"
        ):
            live_research = research_agent.collect_youtube(territory["label"])

        # Local research is deliberately excluded from channel-intelligence
        # runs so the configured channel niche cannot contaminate a universal
        # research request.
        research = research_agent.normalize(reference_research + live_research)
        STATE["research_count"] = len(research)

        if reference_research and live_research:
            STATE["research_source"] = "Reference channels + wider YouTube validation"
        elif reference_research:
            STATE["research_source"] = "Reference channels"
        elif live_research:
            STATE["research_source"] = "Wider YouTube validation"
        else:
            STATE["research_source"] = (
                "No live research collected — check channel URLs and YOUTUBE_API_KEY"
            )

        STATE["completed_steps"].append("research")

        intelligence = {}
        if os.getenv("ANTHROPIC_API_KEY") and research:
            from src.intelligence import IntelligenceAgent

            intelligence = IntelligenceAgent(config).analyze(
                research,
                territory,
            )
            write_json("intelligence.json", intelligence)
        STATE["completed_steps"].append("intelligence")

        STATE["current_step"] = "opportunity"
        opportunities = OpportunityEngine(config).generate(
            research,
            intelligence,
            territory,
        )
        STATE["opportunity_count"] = len(opportunities)
        STATE["opportunities"] = [
            public_opportunity(item) for item in opportunities[:20]
        ]
        write_json("research.json", research)
        write_json("opportunities.json", opportunities)
        STATE["completed_steps"].append("opportunity")

        STATE["current_step"] = "strategy"
        strategy = StrategyAgent(config).build(opportunities)
        write_json("strategy.json", strategy)
        STATE["completed_steps"].append("strategy")

        write_summary(config.name, len(research), opportunities, strategy)
        STATE["current_step"] = None
        STATE["status"] = "completed"
        STATE["completed_at"] = now()
    except Exception as exc:
        STATE["errors"].append(f"{type(exc).__name__}: {exc}")
        STATE["status"] = "failed"
        STATE["current_step"] = None
        STATE["completed_at"] = now()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self.send_json({"status": "ok", "service": "overseer", "timestamp": now()})
            return
        if path == "/api/status":
            self.send_json(STATE)
            return
        if path == "/api/opportunities":
            self.send_json({"opportunities": STATE["opportunities"]})
            return

        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        file_path = (WEB / relative).resolve()
        if WEB not in file_path.parents and file_path != WEB:
            self.send_error(403)
            return
        if not file_path.is_file():
            self.send_error(404)
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/run":
            if STATE["status"] == "running":
                self.send_json(
                    {
                        "ok": False,
                        "message": "Overseer is already running.",
                        "state": STATE,
                    },
                    409,
                )
                return

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                payload = {}

            research_mode = (
                str(payload.get("mode", "channel_intelligence")).strip()
                or "channel_intelligence"
            )
            channel_urls = payload.get("channels", [])
            if isinstance(channel_urls, str):
                channel_urls = [
                    line.strip()
                    for line in channel_urls.splitlines()
                    if line.strip()
                ]
            if not isinstance(channel_urls, list):
                channel_urls = []

            if not channel_urls:
                self.send_json(
                    {
                        "ok": False,
                        "message": "Add at least one reference YouTube channel.",
                    },
                    400,
                )
                return

            run_id = uuid.uuid4().hex[:10]
            threading.Thread(
                target=run_overseer,
                args=(run_id, research_mode, channel_urls),
                daemon=True,
            ).start()
            self.send_json(
                {
                    "ok": True,
                    "run_id": run_id,
                    "mode": research_mode,
                    "channels": channel_urls,
                }
            )
            return
        self.send_error(404)

    def log_message(self, format, *args):
        print(f"[overseer] {self.address_string()} - {format % args}")


def main():
    port = int(os.getenv("OVERSEER_PORT", "3000"))
    print(f"Overseer local control center: http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
