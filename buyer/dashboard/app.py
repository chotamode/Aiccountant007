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

import hmac
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from buyer.events_bus import DEFAULT_EVENTS_PATH, EventBus
from common.events import Actor, Event, EventType

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_HTML_PATH = Path(__file__).parent / "index.html"
LANDING_HTML_PATH = REPO_ROOT / "docs" / "landing" / "index.html"
WIKI_DIR = REPO_ROOT / "docs" / "wiki"
PRESENTATION_DIR = REPO_ROOT / "docs" / "presentation"
VIDEO_DIR = REPO_ROOT / "docs" / "video"
VOICE_DIR = VIDEO_DIR / "voice"

# Global lock for scenario runs to avoid overlapping executions
_run_lock = threading.Lock()


def get_seller_endpoints() -> tuple[str, str]:
    """Return (honest_url, sloppy_url) based on environment, docker network or probe."""
    import urllib.request

    def is_ok(url: str) -> bool:
        try:
            with urllib.request.urlopen(f"{url.rstrip('/')}/availability", timeout=0.8) as resp:
                return resp.status == 200
        except Exception:  # noqa: BLE001
            return False

    env_urls = os.environ.get("SELLER_URLS")
    if env_urls:
        parts = [u.strip() for u in env_urls.split(",") if u.strip()]
        if len(parts) >= 2:
            p0, p1 = parts[0], parts[1]
            if "sloppy" in p0.lower() or "cheap" in p0.lower():
                return p1, p0
            return p0, p1

    if is_ok("http://seller-honest:8001") and is_ok("http://seller-sloppy:8002"):
        return "http://seller-honest:8001", "http://seller-sloppy:8002"

    if is_ok("http://aicc-seller-honest:8001") and is_ok("http://aicc-seller-sloppy:8002"):
        return "http://aicc-seller-honest:8001", "http://aicc-seller-sloppy:8002"

    if is_ok("https://proucetni.tzhk.dev") and is_ok("https://cheapbooks.tzhk.dev"):
        return "https://proucetni.tzhk.dev", "https://cheapbooks.tzhk.dev"

    return "http://127.0.0.1:8003", "http://127.0.0.1:8002"


def ensure_seller_services() -> None:
    """Ensure honest and sloppy seller agents are reachable."""
    honest_url, sloppy_url = get_seller_endpoints()

    import urllib.request

    def is_up(url: str) -> bool:
        try:
            with urllib.request.urlopen(f"{url.rstrip('/')}/availability", timeout=0.8) as resp:
                return resp.status == 200
        except Exception:  # noqa: BLE001 - any failure means "not up yet"
            return False

    if is_up(honest_url) and is_up(sloppy_url):
        return

    python_bin = sys.executable
    env_base = os.environ.copy()
    env_base["PAYMENT_MODE"] = "off"

    if not is_up("http://127.0.0.1:8003"):
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

    if not is_up("http://127.0.0.1:8002"):
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
        if is_up("http://127.0.0.1:8003") and is_up("http://127.0.0.1:8002"):
            break
        time.sleep(0.1)


def is_real_mode() -> bool:
    """Contract C4: True when connected to real Masumi Payment Service node."""
    return bool(os.environ.get("PAYMENT_SERVICE_URL") and os.environ.get("PAYMENT_API_KEY"))


def _run_dir(state_dir: Path, real: bool) -> Path:
    """Create directory for scenario run.
    
    In real mode (Contract C5), policy.sqlite is persistent and NOT wiped on every click.
    In simulation mode, each run gets an isolated clean directory.
    """
    if real:
        real_dir = state_dir / "real_state"
        real_dir.mkdir(parents=True, exist_ok=True)
        return real_dir

    import shutil
    import uuid

    runs_root = state_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    for old in runs_root.iterdir():
        shutil.rmtree(old, ignore_errors=True)
    run_dir = runs_root / uuid.uuid4().hex[:12]
    run_dir.mkdir()
    return run_dir


def execute_scenario_background(scenario: str, state_dir: Path, bus: EventBus | None = None) -> None:
    """Run an audit scenario in a background worker thread, publishing events to the bus."""
    with _run_lock:
        try:
            ensure_seller_services()

            import dataclasses

            from buyer.orchestrator import build_buyer, run_demo
            from buyer.vault import load_documents

            honest_url, sloppy_url = get_seller_endpoints()
            env = os.environ.copy()
            env["SELLER_URLS"] = f"{sloppy_url},{honest_url}"
            invoices_dir = REPO_ROOT / "data" / "invoices"

            real = is_real_mode()
            buyer = build_buyer(_run_dir(state_dir, real), pace=0.08, env=env)
            # Publish into the feed the dashboard is streaming, not the per-run copy.
            buyer = dataclasses.replace(buyer, bus=bus or EventBus(state_dir / "events.jsonl"))
            docs = {d.filename[:2]: d for d in load_documents(invoices_dir, "*.isdoc")}

            def batch(*numbers: str):
                return [docs[n] for n in numbers if n in docs]

            if scenario == "demo":
                run_demo(buyer, invoices_dir, refund_timeout=0.0)

            elif scenario == "honest":
                buyer = dataclasses.replace(buyer, seller_urls=[honest_url])
                buyer.run_deal("September invoices, batch 2 (Honest Audit)", batch("04", "05", "06", "08"))

            elif scenario == "sloppy":
                buyer = dataclasses.replace(buyer, seller_urls=[sloppy_url])
                deal = buyer.run_deal("September invoices, batch 1 (Sloppy Audit)", batch("01", "02", "03", "07"))
                buyer.settle_refund(deal, timeout=0.0)

            elif scenario == "injection":
                if "08" in docs:
                    buyer.attack_drill("Injection simulation drill", docs["08"])

            elif scenario == "duplicate":
                # Pay for the batch once, then resubmit it: the wallet policy must block the second payment.
                buyer = dataclasses.replace(buyer, seller_urls=[honest_url])
                buyer.run_deal("September invoices, batch 2", batch("04", "05"))
                buyer.run_deal("Batch 2 duplicate resubmission attempt", batch("04", "05"))

        except Exception:  # noqa: BLE001 - background thread: log and keep the server alive
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

    if VIDEO_DIR.exists():
        app.mount("/video", StaticFiles(directory=str(VIDEO_DIR)), name="video")

    if WIKI_DIR.exists():
        app.mount("/wiki", StaticFiles(directory=str(WIKI_DIR), html=True), name="wiki")

    if PRESENTATION_DIR.exists():
        app.mount("/presentation", StaticFiles(directory=str(PRESENTATION_DIR), html=True), name="presentation")

    @app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
    def favicon() -> Response:
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text y="24" font-size="24">🛡️</text></svg>"""
        return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})

    @app.api_route("/dashboard", methods=["GET", "HEAD"], response_class=HTMLResponse)
    @app.api_route("/console", methods=["GET", "HEAD"], response_class=HTMLResponse)
    def dashboard_route() -> str:
        if not INDEX_HTML_PATH.exists():
            raise HTTPException(status_code=404, detail="Dashboard index.html not found")
        return INDEX_HTML_PATH.read_text("utf-8")

    @app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
    @app.api_route("/landing", methods=["GET", "HEAD"], response_class=HTMLResponse)
    def landing_route() -> str:
        if not LANDING_HTML_PATH.exists():
            return dashboard_route()
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

    def _verify_admin_token(request: Request) -> None:
        """Contract C5: In real mode, require valid X-Admin-Token header."""
        if not is_real_mode():
            return
        expected = os.environ.get("DASHBOARD_ADMIN_TOKEN", "").strip()
        if not expected:
            raise HTTPException(status_code=403, detail="DASHBOARD_ADMIN_TOKEN not set on server")
        provided = request.headers.get("X-Admin-Token", "").strip()
        if not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
            raise HTTPException(status_code=403, detail="Forbidden: invalid admin token")

    @app.get("/api/mode")
    def get_mode() -> dict[str, Any]:
        """Contract C5: report mode and network."""
        return {
            "real": is_real_mode(),
            "network": os.environ.get("NETWORK", "Preprod"),
        }

    @app.post("/approve/{deal_id}")
    def approve(deal_id: str, request: Request) -> dict[str, Any]:
        _verify_admin_token(request)
        event = Event(
            actor=Actor.BUYER,
            type=EventType.HUMAN_APPROVED,
            msg=f"Human approved deal {deal_id}",
            deal_id=deal_id,
        )
        bus.publish(event)
        return {"status": "ok", "deal_id": deal_id}

    @app.post("/api/run-scenario")
    def run_scenario(request: Request, scenario: str = Query("demo")) -> dict[str, Any]:
        """Trigger an audit scenario in a non-blocking background thread.
        
        Contract C5: protected by X-Admin-Token in real mode.
        Returns 409 if a scenario is already in progress.
        """
        _verify_admin_token(request)
        if _run_lock.locked():
            raise HTTPException(status_code=409, detail="Another scenario is currently running")

        thread = threading.Thread(
            target=execute_scenario_background,
            args=(scenario, state_dir, bus),
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
    uvicorn.run(
        create_dashboard_app(),
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
