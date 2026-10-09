"""Dashboard web server for the buyer agent (task B6 + Impeccable Workbench).

Serves:
    GET /                  -> Landing page (docs/landing/index.html)
    GET /landing           -> Landing page
    GET /dashboard         -> Forensic Escrow Console (buyer/dashboard/index.html)
    GET /console           -> Console alias
    GET /wiki              -> Wiki knowledge base (docs/wiki/index.html)
    GET /presentation      -> Pitch deck viewer (docs/presentation/index.html)
    GET /events            -> Live SSE event stream (Event.to_sse())
    POST /approve/{deal_id}-> Emits HUMAN_APPROVED event to the bus
    POST /api/run-scenario -> Triggers execution of live audit scenarios
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from buyer.events_bus import DEFAULT_EVENTS_PATH, EventBus
from common.events import Actor, Event, EventType

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_HTML_PATH = Path(__file__).parent / "index.html"
LANDING_HTML_PATH = REPO_ROOT / "docs" / "landing" / "index.html"
WIKI_DIR = REPO_ROOT / "docs" / "wiki"
PRESENTATION_DIR = REPO_ROOT / "docs" / "presentation"
VOICE_DIR = REPO_ROOT / "docs" / "video" / "voice"

# Global lock for scenario runs to avoid overlapping executions
_run_lock = threading.Lock()


def ensure_seller_services() -> None:
    """Ensure honest and sloppy seller agents are listening on 8003 and 8002."""
    import urllib.request

    python_bin = sys.executable

    def is_up(port: int) -> bool:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/availability", timeout=0.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    env_base = os.environ.copy()
    env_base["PAYMENT_MODE"] = "off"

    if not is_up(8003):
        env_h = env_base.copy()
        env_h["FIRM_PROFILE"] = "honest"
        env_h["PORT"] = "8003"
        subprocess.Popen(
            [python_bin, "-m", "seller.app"],
            cwd=str(REPO_ROOT),
            env=env_h,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    if not is_up(8002):
        env_s = env_base.copy()
        env_s["FIRM_PROFILE"] = "sloppy"
        env_s["PORT"] = "8002"
        subprocess.Popen(
            [python_bin, "-m", "seller.app"],
            cwd=str(REPO_ROOT),
            env=env_s,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Wait briefly for startup
    for _ in range(15):
        if is_up(8003) and is_up(8002):
            break
        time.sleep(0.1)


def execute_scenario_background(scenario: str, state_dir: Path) -> None:
    """Run an audit scenario in a background worker thread, publishing events to the bus."""
    with _run_lock:
        try:
            ensure_seller_services()

            from buyer.orchestrator import DealStatus, build_buyer, run_demo
            from buyer.vault import load_documents

            env = os.environ.copy()
            env["SELLER_URLS"] = "http://127.0.0.1:8002,http://127.0.0.1:8003"
            invoices_dir = REPO_ROOT / "data" / "invoices"

            buyer = build_buyer(state_dir, pace=0.1, env=env)
            docs = {d.filename[:2]: d for d in load_documents(invoices_dir, "*.isdoc")}

            def batch(*numbers: str):
                return [docs[n] for n in numbers if n in docs]

            if scenario == "demo":
                run_demo(buyer, invoices_dir, refund_timeout=0.0)

            elif scenario == "honest":
                buyer.run_deal("September invoices, batch 2 (Honest Audit)", batch("04", "05", "06", "08"))

            elif scenario == "sloppy":
                deal = buyer.run_deal("September invoices, batch 1 (Sloppy Audit)", batch("01", "02", "03", "07"))
                buyer.settle_refund(deal, timeout=0.0)

            elif scenario == "injection":
                if "08" in docs:
                    buyer.attack_drill("Injection simulation drill", docs["08"])

            elif scenario == "duplicate":
                # Resubmit previously processed invoices
                buyer.run_deal("Batch 2 duplicate resubmission attempt", batch("04", "05"))

        except Exception as exc:
            import traceback

            traceback.print_exc()


def create_dashboard_app(bus: EventBus | None = None) -> FastAPI:
    events_path = Path(os.environ.get("EVENTS_PATH", DEFAULT_EVENTS_PATH))
    state_dir = events_path.parent
    state_dir.mkdir(parents=True, exist_ok=True)
    bus = bus or EventBus(events_path)

    app = FastAPI(title="Aiccountant007 Forensic Console")

    if VOICE_DIR.exists():
        app.mount("/voice", StaticFiles(directory=str(VOICE_DIR)), name="voice")

    if WIKI_DIR.exists():
        app.mount("/wiki", StaticFiles(directory=str(WIKI_DIR), html=True), name="wiki")

    if PRESENTATION_DIR.exists():
        app.mount("/presentation", StaticFiles(directory=str(PRESENTATION_DIR), html=True), name="presentation")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    @app.get("/console", response_class=HTMLResponse)
    def dashboard_route() -> str:
        if not INDEX_HTML_PATH.exists():
            raise HTTPException(status_code=404, detail="Dashboard index.html not found")
        return INDEX_HTML_PATH.read_text("utf-8")

    @app.get("/landing", response_class=HTMLResponse)
    def landing_route() -> str:
        if not LANDING_HTML_PATH.exists():
            raise HTTPException(status_code=404, detail="Landing page not found")
        return LANDING_HTML_PATH.read_text("utf-8")

    @app.get("/events")
    async def events(request: Request) -> StreamingResponse:
        async def event_generator():
            async for ev in bus.stream(poll_interval=0.1):
                if await request.is_disconnected():
                    break
                yield ev.to_sse()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/approve/{deal_id}")
    def approve(deal_id: str) -> dict[str, Any]:
        event = Event(
            actor=Actor.BUYER,
            type=EventType.HUMAN_APPROVED,
            msg=f"Human approved deal {deal_id}",
            deal_id=deal_id,
        )
        bus.publish(event)
        return {"status": "ok", "deal_id": deal_id}

    @app.post("/api/run-scenario")
    def run_scenario(scenario: str = Query("demo")) -> dict[str, Any]:
        """Trigger an audit scenario in a non-blocking background thread."""
        thread = threading.Thread(
            target=execute_scenario_background,
            args=(scenario, state_dir),
            daemon=True,
        )
        thread.start()
        return {"status": "dispatched", "scenario": scenario}

    @app.get("/history")
    def history() -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in bus.history()]

    return app


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(create_dashboard_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
