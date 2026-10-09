import asyncio
import tempfile
from pathlib import Path

import pytest

from buyer.events_bus import EventBus
from common.events import Actor, Event, EventType


def test_event_bus_publish_and_history():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"
        bus = EventBus(path)

        ev1 = Event(actor=Actor.BUYER, type=EventType.DOCS_HASHED, msg="1 doc hashed")
        ev2 = Event(actor=Actor.SELLER, type=EventType.JOB_STARTED, msg="started")

        bus.publish(ev1)
        bus.publish(ev2)

        history = bus.history()
        assert len(history) == 2
        assert history[0].type == EventType.DOCS_HASHED
        assert history[1].type == EventType.JOB_STARTED


@pytest.mark.asyncio
async def test_event_bus_stream():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"
        bus = EventBus(path)

        ev1 = Event(actor=Actor.BUYER, type=EventType.DOCS_HASHED, msg="1 doc hashed")
        bus.publish(ev1)

        collected = []

        async def reader():
            async for ev in bus.stream(poll_interval=0.05):
                collected.append(ev)
                if len(collected) == 2:
                    break

        task = asyncio.create_task(reader())
        await asyncio.sleep(0.1)

        ev2 = Event(actor=Actor.SELLER, type=EventType.JOB_STARTED, msg="started")
        bus.publish(ev2)

        await asyncio.wait_for(task, timeout=2.0)
        assert len(collected) == 2
        assert collected[0].type == EventType.DOCS_HASHED
        assert collected[1].type == EventType.JOB_STARTED
