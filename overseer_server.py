from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from src.config import load_channel_config
from src.intent import MAX_PROMPT_CHARS, VIDEO_FORMATS, VIDEO_LENGTHS
from src.memory import MemoryStore
from src.models import Opportunity
from src.output import RUN_FILE, RunWriter, data_path, load_json
from src.pipeline import PipelineError, PipelineOptions, produce_from_run, run_pipeline
from src.qa import unresolved_claims

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
CONFIG = ROOT / "config" / "channel.yaml"
MAX_BODY_BYTES = 64 * 1024
LOCAL_HOSTS = {"localhost", "127.0.0.1"}

log = logging.getLogger("overseer")

# Guards STATE: worker threads write it while request threads read it.
STATE_LOCK = threading.Lock()
STATE: dict = {
    "run_id": None,
    "job": None,
    "status": "idle",
    "started_at": None,
    "completed_at": None,
    "current_step": None,
    "completed_steps": [],
    "errors": [],
    "warnings": [],
    "research_count": 0,
    "opportunity_count": 0,
    "opportunities": [],
    "channel": "Overseer",
    "reference_channels": [],
    "intent": None,
    "channel_profiles": [],
    "research_territory": None,
    "research_source": "",
    "production": None,
    "analytics": None,
    "memory": None,
}


def now():
    return datetime.now(timezone.utc).isoformat()


def update_state(**values):
    with STATE_LOCK:
        STATE.update(values)


def snapshot_state():
    with STATE_LOCK:
        return json.loads(json.dumps(STATE, ensure_ascii=False, default=str))


def public_opportunity(item):
    return {
        "opportunity_id": item.opportunity_id,
        "topic": item.topic,
        "angle": item.angle,
        "tier": item.tier,
        "evidence_count": item.evidence_count,
        "score": round(item.score * 100),
        "demand": round(item.demand_signal * 100),
        "audience_fit": round(item.audience_fit * 100),
        "competition_gap": round(item.competition_gap * 100),
        "differentiation": round(item.differentiation * 100),
        "business_intent": round(item.business_intent * 100),
        "rationale": item.rationale,
        "evidence": item.evidence,
        "history": item.history,
    }


def public_profile(profile):
    return {
        key: profile.get(key)
        for key in (
            "url",
            "channel_id",
            "title",
            "description",
            "subscriber_count",
            "video_count",
            "view_count",
            "country",
            "topic_categories",
        )
    }


def production_summary(run_dir):
    """What the video workspace panel shows for a run's produced opportunity."""
    if run_dir is None:
        return None
    run_dir = Path(run_dir)
    produced = (load_json(run_dir / RUN_FILE, {}) or {}).get("produced")
    if not produced:
        return None

    def read(name):
        return load_json(run_dir / name, {}) or {}

    brief = read("video_brief.json")
    script = read("script.json")
    thumbnails = read("thumbnail_concepts.json")
    qa = read("qa_report.json")
    sections = script.get("sections", []) or []
    return {
        "run_id": run_dir.name,
        "run_path": f"outputs/runs/{run_dir.name}",
        "topic": produced.get("topic", ""),
        "working_title": brief.get("working_title", ""),
        "alternative_titles": brief.get("alternative_titles", [])[:4],
        "viewer_promise": brief.get("viewer_promise", ""),
        "opening_hook": brief.get("opening_hook", ""),
        "outline": brief.get("outline", [])[:12],
        "cta": brief.get("cta", ""),
        "thumbnail_text": brief.get("thumbnail_text", ""),
        "estimated_minutes": script.get("estimated_minutes"),
        "sections": [
            {
                "heading": section.get("heading", ""),
                "preview": str(section.get("narration", ""))[:220],
            }
            for section in sections[:20]
        ],
        "thumbnails": [
            {"name": concept.get("concept_name", ""), "text": concept.get("text", "")}
            for concept in thumbnails.get("concepts", [])[:3]
        ],
        "checks": qa.get("checks", []),
        "claims": qa.get("claims", []),
        "has_brief": bool(brief),
        "has_script": bool(sections),
        "has_plan": (run_dir / "production_plan.json").exists(),
        "has_thumbnails": bool(thumbnails.get("concepts")),
        "failed_checks": qa.get("failed_checks", []),
        "open_claims": len(unresolved_claims(qa)) if qa else 0,
        "fallbacks": [
            name
            for name, payload in (("brief", brief), ("script", script), ("thumbnails", thumbnails))
            if payload.get("fallback_reason")
        ],
    }


def _top_signals(signals, limit=5):
    ranked = sorted(signals.items(), key=lambda pair: pair[1].get("mean", 0), reverse=True)
    return [
        {"name": name, "mean": values.get("mean", 0), "count": int(values.get("count", 0))}
        for name, values in ranked[:limit]
    ]


def learning_summary():
    analytics = load_json(data_path("analytics.json"), {}) or {}
    memory = MemoryStore().load()
    summary = analytics.get("summary", {}) if analytics else {}
    return {
        "analytics": (
            {
                "start_date": analytics.get("start_date"),
                "end_date": analytics.get("end_date"),
                **{key: value for key, value in summary.items() if key != "signals"},
                "top_videos": sorted(
                    summary.get("signals", []),
                    key=lambda video: video.get("views") or 0,
                    reverse=True,
                )[:5],
            }
            if analytics
            else None
        ),
        "memory": {
            "videos_analyzed": memory.videos_analyzed,
            "topics": len(memory.topic_signals),
            "title_patterns": len(memory.title_signals),
            "title_metric": memory.title_metric,
            "formats": len(memory.format_signals),
            "updated_at": memory.updated_at,
            "notes": memory.notes,
            "top_topics": _top_signals(memory.topic_signals),
            "top_titles": _top_signals(memory.title_signals),
            "top_formats": _top_signals(memory.format_signals),
        },
    }


def restore_latest():
    """Show the last completed run after a restart, so ideas can still be produced."""
    try:
        writer = RunWriter.open()
    except FileNotFoundError:
        update_state(**learning_summary())
        return

    run_info = writer.read_json(RUN_FILE, {}) or {}
    opportunities = [
        Opportunity.from_dict(item) for item in writer.read_json("opportunities.json", []) or []
    ]
    update_state(
        run_id=writer.run_id,
        status="completed",
        completed_at=run_info.get("completed_at"),
        completed_steps=["research", "intelligence", "opportunity", "strategy"],
        warnings=run_info.get("warnings", []),
        intent=writer.read_json("intent.json") or None,
        research_count=len(writer.read_json("research.json", []) or []),
        research_territory=writer.read_json("research_territory.json") or None,
        opportunity_count=len(opportunities),
        opportunities=[public_opportunity(item) for item in opportunities[:20]],
        production=production_summary(writer.run_dir),
        **learning_summary(),
    )


def sync_state(event, step, result):
    """Mirror pipeline progress into STATE for the dashboard to poll."""
    with STATE_LOCK:
        if event == "start":
            STATE["current_step"] = step
        else:
            STATE["completed_steps"] = [*STATE["completed_steps"], step]
        STATE["run_id"] = result.run_id
        STATE["intent"] = result.intent or None
        STATE["channel_profiles"] = [public_profile(p) for p in result.channel_profiles]
        STATE["research_territory"] = result.territory or None
        STATE["research_count"] = len(result.research)
        STATE["research_source"] = result.research_source
        STATE["opportunity_count"] = len(result.opportunities)
        STATE["opportunities"] = [public_opportunity(item) for item in result.opportunities[:20]]
        STATE["warnings"] = list(result.warnings)


def sync_production(event, step, result):
    with STATE_LOCK:
        if event == "start":
            STATE["current_step"] = step
        else:
            STATE["completed_steps"] = [*STATE["completed_steps"], step]
        STATE["warnings"] = list(result.warnings)


def _finish(error=None):
    with STATE_LOCK:
        STATE["current_step"] = None
        STATE["completed_at"] = now()
        if error:
            STATE["status"] = "failed"
            STATE["errors"] = [*STATE["errors"], error]
        else:
            STATE["status"] = "completed"


def run_research(channel_urls, prompt="", video_format="", video_length=""):
    update_state(
        job="research",
        started_at=now(),
        completed_at=None,
        current_step="research",
        completed_steps=[],
        errors=[],
        warnings=[],
        intent=None,
        research_count=0,
        opportunity_count=0,
        opportunities=[],
        reference_channels=channel_urls,
        channel_profiles=[],
        research_territory=None,
        research_source="",
        production=None,
    )
    try:
        config = load_channel_config(str(CONFIG))
        # Local research is deliberately left out of dashboard runs so the
        # configured channel niche cannot contaminate the research request.
        options = PipelineOptions(
            channels=channel_urls,
            prompt=prompt,
            video_format=video_format,
            video_length=video_length,
        )
        run_pipeline(config, options, on_progress=sync_state)
        _finish()
    except PipelineError as exc:
        _finish(str(exc))
    except Exception as exc:
        log.exception("research run failed")
        _finish(f"{type(exc).__name__}: {exc}")


def run_production(opportunity_index):
    update_state(
        job="produce",
        started_at=now(),
        completed_at=None,
        current_step="brief",
        completed_steps=["research", "intelligence", "opportunity", "strategy"],
        errors=[],
    )
    try:
        config = load_channel_config(str(CONFIG))
        result = produce_from_run(
            config,
            opportunity_index,
            run_id=STATE.get("run_id"),
            on_progress=sync_production,
        )
        update_state(production=production_summary(result.run_dir))
        _finish()
    except PipelineError as exc:
        _finish(str(exc))
    except Exception as exc:
        log.exception("production run failed")
        _finish(f"{type(exc).__name__}: {exc}")


def start_job(target, *args):
    """Start a background job unless one is running. Returns False when busy."""
    with STATE_LOCK:
        if STATE["status"] == "running":
            return False
        # Claim the slot before the thread starts so a second request is refused.
        STATE["status"] = "running"
    threading.Thread(target=target, args=args, daemon=True).start()
    return True


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _local_host_header(self):
        # Rejects DNS-rebinding requests that reach 127.0.0.1 under another name.
        host = self.headers.get("Host", "")
        return urlparse(f"http://{host}").hostname in LOCAL_HOSTS

    def do_GET(self):
        if not self._local_host_header():
            self.send_error(403)
            return
        path = urlparse(self.path).path
        if path == "/api/health":
            self.send_json({"status": "ok", "service": "overseer", "timestamp": now()})
            return
        if path == "/api/status":
            self.send_json(snapshot_state())
            return
        if path == "/api/opportunities":
            self.send_json({"opportunities": snapshot_state()["opportunities"]})
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

    def _read_trusted_json(self):
        """Return the JSON body of a same-origin request, or None after replying."""
        if not self._local_host_header():
            self.send_json({"ok": False, "message": "Forbidden host."}, 403)
            return None
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in LOCAL_HOSTS:
            self.send_json({"ok": False, "message": "Cross-site requests are not allowed."}, 403)
            return None
        # Requiring JSON forces a CORS preflight for cross-site pages, which
        # this server never approves; a text/plain "simple request" is refused.
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self.send_json({"ok": False, "message": "Content-Type must be application/json."}, 415)
            return None

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self.send_json({"ok": False, "message": "Invalid request size."}, 400)
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if not isinstance(payload, dict):
            self.send_json({"ok": False, "message": "Body must be a JSON object."}, 400)
            return None
        return payload

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/run", "/api/produce"):
            self.send_error(404)
            return
        payload = self._read_trusted_json()
        if payload is None:
            return

        if path == "/api/run":
            channel_urls = payload.get("channels", [])
            if isinstance(channel_urls, str):
                channel_urls = channel_urls.splitlines()
            if not isinstance(channel_urls, list):
                channel_urls = []
            channel_urls = [str(url).strip() for url in channel_urls if str(url).strip()][:10]
            prompt = str(payload.get("prompt") or "").strip()
            video_format = str(payload.get("format") or "")
            video_length = str(payload.get("length") or "")
            problem = None
            if not prompt and not channel_urls:
                problem = "Describe the video you want to make, or add a reference channel."
            elif len(prompt) > MAX_PROMPT_CHARS:
                problem = f"Keep the description under {MAX_PROMPT_CHARS} characters."
            elif video_format and video_format not in VIDEO_FORMATS:
                problem = "Unknown video format."
            elif video_length and video_length not in VIDEO_LENGTHS:
                problem = "Unknown video length."
            if problem:
                self.send_json({"ok": False, "message": problem}, 400)
                return
            if not start_job(run_research, channel_urls, prompt, video_format, video_length):
                self.send_json({"ok": False, "message": "Overseer is already running."}, 409)
                return
            self.send_json({"ok": True, "channels": channel_urls, "prompt": prompt})
            return

        index = payload.get("opportunity")
        available = len(snapshot_state()["opportunities"])
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < available:
            self.send_json({"ok": False, "message": "Choose an opportunity from the latest run."}, 400)
            return
        if not start_job(run_production, index):
            self.send_json({"ok": False, "message": "Overseer is already running."}, 409)
            return
        self.send_json({"ok": True, "opportunity": index})

    def log_message(self, format, *args):
        log.info("%s - %s", self.address_string(), format % args)


def main():
    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        update_state(channel=load_channel_config(str(CONFIG)).name)
    except (OSError, KeyError):
        pass
    restore_latest()
    port = int(os.getenv("OVERSEER_PORT", "3000"))
    print(f"Overseer local control center: http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
