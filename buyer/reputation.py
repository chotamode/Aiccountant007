"""Seller reputation from deal outcomes, kept in SQLite.

score = (paid + 1) / (total + 2): a new seller starts at 0.5, every refund or
failure pulls the score down. discovery.py drops sellers below MIN_REPUTATION.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

DEFAULT_PRIOR = 0.5
PRIOR_WEIGHT = 2  # the starting value weighs as much as two deals

_SCHEMA = """
CREATE TABLE IF NOT EXISTS outcomes (
    deal_id   TEXT PRIMARY KEY,
    seller_id TEXT NOT NULL,
    outcome   TEXT NOT NULL,
    ts        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS outcomes_by_seller ON outcomes (seller_id);
"""


class Outcome(StrEnum):
    PAID = "paid"  # work verified, escrow goes to the seller
    REFUNDED = "refunded"  # verification failed, refund requested
    FAILED = "failed"  # no usable result at all


class Reputation:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def record(self, seller_id: str, outcome: Outcome | str, deal_id: str) -> bool:
        """Book how a deal ended. A deal counts once: a repeated deal_id returns False."""
        outcome = Outcome(outcome)
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO outcomes (deal_id, seller_id, outcome, ts) VALUES (?, ?, ?, ?)",
                (deal_id, seller_id, outcome.value, datetime.now(UTC).isoformat()),
            )
        return cursor.rowcount == 1

    def deals_seen(self, seller_id: str) -> int:
        return self._counts(seller_id)[1]

    def score(self, seller_id: str, prior: float = DEFAULT_PRIOR) -> float:
        """(paid + 2 * prior) / (total + 2), in 0..1.

        With the default prior this is (paid + 1) / (total + 2). For a Sokosumi
        agent pass prior = metrics.ratings.average / 5 as the starting value.
        """
        if not 0.0 <= prior <= 1.0:
            raise ValueError(f"prior must be within 0..1, got {prior}")
        paid, total = self._counts(seller_id)
        return (paid + PRIOR_WEIGHT * prior) / (total + PRIOR_WEIGHT)

    def _counts(self, seller_id: str) -> tuple[int, int]:
        with self._lock:
            paid, total = self._conn.execute(
                "SELECT COALESCE(SUM(outcome = ?), 0), COUNT(*) FROM outcomes WHERE seller_id = ?",
                (Outcome.PAID.value, seller_id),
            ).fetchone()
        return paid, total

    def close(self) -> None:
        self._conn.close()
