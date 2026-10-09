"""Event bus for the dashboard: one JSON line per common.Event in a shared file.

The orchestrator (python -m buyer.orchestrator) and the dashboard server are
separate processes, so the file is the bus. Anyone appends with publish();
history() and stream() read it back, stream() also follows new lines written by
other processes. Default path: buyer/state/events.jsonl (gitignored).
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from collections.abc import AsyncIterator
from pathlib import Path

from pydantic import ValidationError

from common.events import Event

DEFAULT_EVENTS_PATH = Path("buyer/state/events.jsonl")

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self, path: Path = DEFAULT_EVENTS_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def publish(self, event: Event) -> Event:
        """Append the event as one line. Safe from many threads and many processes."""
        data = memoryview((event.model_dump_json() + "\n").encode("utf-8"))
        # One unbuffered write() on an O_APPEND file keeps a line whole even when
        # another process appends at the same moment.
        with self._lock, self.path.open("ab", buffering=0) as file:
            while data:
                data = data[file.write(data) :]
        return event

    def history(self) -> list[Event]:
        """All complete, valid events in the file, in publication order."""
        return self._read_new(_Cursor())[0]

    async def stream(self, poll_interval: float = 0.3) -> AsyncIterator[Event]:
        """Replay the history, then yield events appended by any process, forever."""
        cursor = _Cursor()
        while True:
            events, cursor = self._read_new(cursor)
            for event in events:
                yield event
            await asyncio.sleep(poll_interval)

    def _read_new(self, cursor: _Cursor) -> tuple[list[Event], _Cursor]:
        """Events after cursor.offset. A line without its newline yet is left for the next call."""
        try:
            with self.path.open("rb") as file:
                info = os.fstat(file.fileno())
                offset = cursor.offset
                if info.st_ino != cursor.inode or info.st_size < offset:
                    offset = 0  # the file was deleted, replaced or truncated: start over
                file.seek(offset)
                chunk = file.read()
        except FileNotFoundError:
            return [], _Cursor()
        complete, newline, _unfinished = chunk.rpartition(b"\n")
        if not newline:
            return [], _Cursor(info.st_ino, offset)
        events = [event for line in complete.split(b"\n") if (event := _parse_line(line))]
        return events, _Cursor(info.st_ino, offset + len(complete) + 1)


class _Cursor:
    """Where the reader stopped: file identity plus byte offset."""

    __slots__ = ("inode", "offset")

    def __init__(self, inode: int = 0, offset: int = 0) -> None:
        self.inode = inode
        self.offset = offset


def _parse_line(line: bytes) -> Event | None:
    if not line.strip():
        return None
    try:
        return Event.model_validate_json(line)
    except ValidationError:
        logger.warning("events bus: skipped a line that is not an Event: %.80r", line)
        return None
