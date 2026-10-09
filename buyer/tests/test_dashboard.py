import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from buyer.dashboard.app import create_dashboard_app
from buyer.events_bus import EventBus
from common.events import Actor, Event, EventType


def test_dashboard_index():
    app = create_dashboard_app()
    client = TestClient(app)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Aiccountant007" in response.text
    assert "Live Event Stream" in response.text


def test_root_serves_landing_and_video():
    client = TestClient(create_dashboard_app())
    assert client.get("/").text == client.get("/landing").text
    video = client.get("/video/Aiccountant007_Demo_90s.mp4", headers={"Range": "bytes=0-15"})
    assert video.status_code in (200, 206)


def test_dashboard_history():
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.jsonl"
        bus = EventBus(events_path)
        app = create_dashboard_app(bus=bus)
        client = TestClient(app)

        ev1 = Event(actor=Actor.BUYER, type=EventType.DOCS_HASHED, msg="1 doc hashed", deal_id="d1")
        ev2 = Event(actor=Actor.SELLER, type=EventType.ESCROW_LOCKED, msg="locked", simulated=True, tx_url="https://tx/123", deal_id="d1")
        ev3 = Event(actor=Actor.BUYER, type=EventType.VERIFICATION_PASSED, msg="verified", deal_id="d1")

        bus.publish(ev1)
        bus.publish(ev2)
        bus.publish(ev3)

        history = client.get("/history").json()
        assert len(history) == 3
        assert history[0]["msg"] == "1 doc hashed"
        assert history[1]["simulated"] is True
        assert history[1]["tx_url"] == "https://tx/123"


@pytest.mark.asyncio
async def test_dashboard_events_stream():
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.jsonl"
        bus = EventBus(events_path)

        ev1 = Event(actor=Actor.BUYER, type=EventType.DOCS_HASHED, msg="1 doc hashed", deal_id="d1")
        ev2 = Event(actor=Actor.SELLER, type=EventType.ESCROW_LOCKED, msg="locked", simulated=True, tx_url="https://tx/123", deal_id="d1")
        ev3 = Event(actor=Actor.BUYER, type=EventType.VERIFICATION_PASSED, msg="verified", deal_id="d1")

        bus.publish(ev1)
        bus.publish(ev2)
        bus.publish(ev3)

        collected = []
        async for ev in bus.stream(poll_interval=0.05):
            collected.append(ev)
            if len(collected) == 3:
                break

        assert len(collected) == 3
        assert collected[0].msg == "1 doc hashed"
        assert collected[1].simulated is True
        assert collected[1].tx_url == "https://tx/123"
        assert collected[2].type == EventType.VERIFICATION_PASSED
        assert collected[0].to_sse().startswith("event: docs_hashed\ndata:")


def test_dashboard_human_approval():
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.jsonl"
        bus = EventBus(events_path)
        app = create_dashboard_app(bus=bus)
        client = TestClient(app)

        resp = client.post("/approve/deal-xyz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "deal_id": "deal-xyz"}

        history = bus.history()
        assert len(history) == 1
        assert history[0].type == EventType.HUMAN_APPROVED
        assert history[0].deal_id == "deal-xyz"


def test_dashboard_voice_static():
    app = create_dashboard_app()
    client = TestClient(app)
    # Check that voice static endpoint returns the audio clip
    resp = client.get("/voice/01_intro.mp3")
    assert resp.status_code == 200
    assert resp.headers["content-type"] in ("audio/mpeg", "audio/mp3", "application/octet-stream")


def test_landing_and_docs_endpoints():
    app = create_dashboard_app()
    client = TestClient(app)

    # Test landing page
    resp_landing = client.get("/landing")
    assert resp_landing.status_code == 200
    assert "Aiccountant007" in resp_landing.text
    assert "B2B AI Agents Trade" in resp_landing.text

    # Test wiki
    resp_wiki = client.get("/wiki/")
    assert resp_wiki.status_code == 200
    assert "Aiccountant007" in resp_wiki.text

    # Test presentation
    resp_deck = client.get("/presentation/")
    assert resp_deck.status_code == 200
    assert "Aiccountant007 Pitch Deck" in resp_deck.text

    # Test api run-scenario dispatch
    resp_api = client.post("/api/run-scenario?scenario=demo")
    assert resp_api.status_code == 200
    assert resp_api.json()["status"] == "dispatched"

    # Test HEAD requests
    assert client.head("/").status_code == 200
    assert client.head("/dashboard").status_code == 200
    assert client.head("/favicon.ico").status_code == 200

    # Test favicon content
    resp_fav = client.get("/favicon.ico")
    assert resp_fav.status_code == 200
    assert "svg" in resp_fav.text

