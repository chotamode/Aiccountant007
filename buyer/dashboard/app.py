"""Dashboard web server for the buyer agent (task B6).

Serves the live SSE feed from buyer/state/events.jsonl, the dashboard UI,
and the human approval endpoint:
    GET /           -> index.html
    GET /events     -> SSE stream (Event.to_sse())
    POST /approve/{deal_id} -> emits HUMAN_APPROVED event to the bus
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from buyer.events_bus import DEFAULT_EVENTS_PATH, EventBus
from common.events import Actor, Event, EventType

INDEX_HTML_PATH = Path(__file__).parent / "index.html"


def create_dashboard_app(bus: EventBus | None = None) -> FastAPI:
    events_path = Path(os.environ.get("EVENTS_PATH", DEFAULT_EVENTS_PATH))
    bus = bus or EventBus(events_path)

    app = FastAPI(title="Aiccountant007 Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        if not INDEX_HTML_PATH.exists():
            raise HTTPException(status_code=404, detail="index.html not found")
        return INDEX_HTML_PATH.read_text("utf-8")

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
