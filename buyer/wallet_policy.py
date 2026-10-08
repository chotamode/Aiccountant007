"""Spending policy of the client's agent: hard limits and pay-once, enforced in code.

Runs before every payment (docs/ARCHITECTURE.md section 6). Neither an LLM nor
the text of a document can talk it into paying: the amount must equal the offer
price, stay within the per-task and monthly limits, and no document is paid
twice. State lives in SQLite, so a crash or a restart cannot cause a second
payment.

    decision = policy.reserve(deal_id, offer, amount, doc_hashes, blockchain_identifier=...)
    if decision.approved:          # only now may money move: POST /purchase
        ...
    policy.mark_paid(deal_id)      # work verified
    policy.mark_refunded(deal_id)  # money came back, documents may be paid again
    policy.release(deal_id)        # purchase never locked any funds

Use a fresh deal_id for every purchase attempt: a known deal_id is always blocked.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from common.market import Offer, Price, PriceUnit

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    deal_id               TEXT PRIMARY KEY,
    seller_id             TEXT NOT NULL,
    amount                INTEGER NOT NULL,
    unit                  TEXT NOT NULL,
    status                TEXT NOT NULL,
    blockchain_identifier TEXT UNIQUE,
    human_approved        INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paid_documents (
    doc_hash TEXT PRIMARY KEY,
    deal_id  TEXT NOT NULL REFERENCES deals (deal_id),
    status   TEXT NOT NULL
);
"""


class DecisionStatus(StrEnum):
    APPROVED = "approved"
    BLOCKED = "blocked"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"


class Reason(StrEnum):
    OK = "ok"
    HUMAN_THRESHOLD = "human_threshold"  # at or above the threshold, a human has to approve
    PRICE_MISMATCH = "price_mismatch"  # asked to pay something other than the offer price
    PER_TASK_LIMIT = "per_task_limit"
    MONTHLY_LIMIT = "monthly_limit"
    DUPLICATE = "duplicate"  # every document is already paid or in work
    UNIT_MISMATCH = "unit_mismatch"  # offer priced in a unit this wallet does not spend
    DEAL_EXISTS = "deal_exists"  # this deal or blockchain identifier was reserved before
    INVALID_REQUEST = "invalid_request"


class DealStatus(StrEnum):
    RESERVED = "reserved"  # set before POST /purchase
    PAID = "paid"
    REFUNDED = "refunded"
    RELEASED = "released"  # reserved, but no funds were ever locked


# A document in one of these states belongs to a live deal and must not be paid again.
_HELD = (DealStatus.RESERVED.value, DealStatus.PAID.value)


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: DecisionStatus
    reason: Reason
    message: str
    violations: list[Reason] = Field(default_factory=list)  # every broken money rule, reason is the first
    payable_doc_hashes: list[str] = Field(default_factory=list)
    duplicate_doc_hashes: list[str] = Field(default_factory=list)

    @property
    def approved(self) -> bool:
        return self.status == DecisionStatus.APPROVED


class WalletPolicy:
    """Limits are integers in the smallest unit of `unit` (lovelace by default)."""

    def __init__(
        self,
        db_path: str | Path,
        monthly_limit: int,
        max_per_task: int,
        human_threshold: int,
        *,
        unit: PriceUnit = PriceUnit.LOVELACE,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        limits = {"monthly_limit": monthly_limit, "max_per_task": max_per_task, "human_threshold": human_threshold}
        for name, value in limits.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
        self.monthly_limit = monthly_limit
        self.max_per_task = max_per_task
        self.human_threshold = human_threshold
        self.unit = unit
        self._now = now or (lambda: datetime.now(UTC))
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: transactions are opened explicitly with BEGIN IMMEDIATE.
        self._conn = sqlite3.connect(str(db_path), timeout=10, isolation_level=None, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> WalletPolicy:
        """Limits from POLICY_*_LOVELACE. A missing limit is an error: no limit, no spending."""
        env = os.environ if env is None else env

        def limit(name: str) -> int:
            value = env.get(name, "").strip()
            if not value:
                raise ValueError(f"{name} is not set: refusing to spend without a limit")
            return int(value)

        return cls(
            env.get("POLICY_DB_PATH") or "buyer/state/policy.sqlite",
            monthly_limit=limit("POLICY_MONTHLY_LIMIT_LOVELACE"),
            max_per_task=limit("POLICY_MAX_PER_TASK_LOVELACE"),
            human_threshold=limit("POLICY_HUMAN_APPROVAL_THRESHOLD_LOVELACE"),
        )

    # --- decisions ---

    def check(
        self,
        deal_id: str,
        offer: Offer,
        requested_amount: int,
        doc_hashes: Sequence[str],
        *,
        human_approved: bool = False,
    ) -> Decision:
        """Dry run of reserve(): the same decision, nothing written."""
        with self._lock:
            return self._decide(deal_id, offer, requested_amount, doc_hashes, None, human_approved)

    def reserve(
        self,
        deal_id: str,
        offer: Offer,
        requested_amount: int,
        doc_hashes: Sequence[str],
        *,
        blockchain_identifier: str | None = None,
        human_approved: bool = False,
    ) -> Decision:
        """Decide and, if approved, reserve the documents in the same SQLite transaction.

        Call it right before POST /purchase and pay only when the result is
        approved. human_approved=True skips the human threshold and nothing else.
        """
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                decision = self._decide(
                    deal_id, offer, requested_amount, doc_hashes, blockchain_identifier, human_approved
                )
                if decision.approved:
                    self._write_reservation(deal_id, offer, decision, blockchain_identifier, human_approved)
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        return decision

    def _decide(
        self,
        deal_id: str,
        offer: Offer,
        requested_amount: int,
        doc_hashes: Sequence[str],
        blockchain_identifier: str | None,
        human_approved: bool,
    ) -> Decision:
        def blocked(reason: Reason, message: str, **extra: list) -> Decision:
            return Decision(status=DecisionStatus.BLOCKED, reason=reason, message=message, **extra)

        known = self._conn.execute("SELECT status FROM deals WHERE deal_id = ?", (deal_id,)).fetchone()
        if known:
            return blocked(Reason.DEAL_EXISTS, f"deal {deal_id} is already {known[0]}")
        if blockchain_identifier is not None:
            owner = self._conn.execute(
                "SELECT deal_id FROM deals WHERE blockchain_identifier = ?", (blockchain_identifier,)
            ).fetchone()
            if owner:
                return blocked(Reason.DEAL_EXISTS, f"blockchain identifier already belongs to deal {owner[0]}")

        hashes = list(doc_hashes)
        if not hashes or not all(isinstance(h, str) and _SHA256.match(h) for h in hashes):
            return blocked(Reason.INVALID_REQUEST, "doc_hashes must be a non-empty list of sha256 hex digests")

        price = offer.price
        if price.unit != self.unit:
            message = f"offer is priced in {price.unit.value}, this wallet only spends {self.unit.value}"
            return blocked(Reason.UNIT_MISMATCH, message, violations=[Reason.UNIT_MISMATCH])

        # Money rules. Limits are checked against the larger of the two amounts,
        # so an inflated request shows every limit it would have broken.
        is_amount = type(requested_amount) is int
        amount = max(requested_amount, price.amount) if is_amount else price.amount
        spent = self._spent_this_month()
        problems: list[tuple[Reason, str]] = []
        if not is_amount or requested_amount != price.amount:
            asked = self._money(requested_amount) if is_amount else repr(requested_amount)
            problems.append((Reason.PRICE_MISMATCH, f"asked to pay {asked}, the offer price is {price}"))
        if amount > self.max_per_task:
            problems.append(
                (Reason.PER_TASK_LIMIT, f"{self._money(amount)} is above the per-task limit {self._money(self.max_per_task)}")
            )
        if spent + amount > self.monthly_limit:
            problems.append(
                (
                    Reason.MONTHLY_LIMIT,
                    f"{self._money(spent)} spent this month, {self._money(amount)} more would exceed "
                    f"the monthly limit {self._money(self.monthly_limit)}",
                )
            )
        if problems:
            return blocked(problems[0][0], "; ".join(m for _, m in problems), violations=[r for r, _ in problems])

        # Pay-once: drop what is already paid or in work, and repeats inside the package.
        held = self._held(hashes)
        payable: list[str] = []
        duplicates: list[str] = []
        for doc_hash in hashes:
            if doc_hash in held or doc_hash in payable:
                duplicates.append(doc_hash)
            else:
                payable.append(doc_hash)
        if not payable:
            message = f"all {len(hashes)} documents are already paid or in work"
            return blocked(Reason.DUPLICATE, message, duplicate_doc_hashes=duplicates)

        hashes_out = {"payable_doc_hashes": payable, "duplicate_doc_hashes": duplicates}
        if amount >= self.human_threshold and not human_approved:
            return Decision(
                status=DecisionStatus.HUMAN_APPROVAL_REQUIRED,
                reason=Reason.HUMAN_THRESHOLD,
                message=f"{price} is at or above the human approval threshold {self._money(self.human_threshold)}",
                **hashes_out,
            )
        return Decision(
            status=DecisionStatus.APPROVED,
            reason=Reason.OK,
            message=(
                f"{price} to {offer.seller.name} for {len(payable)} documents; "
                f"{self._money(spent + amount)} of {self._money(self.monthly_limit)} this month"
            ),
            **hashes_out,
        )

    def _write_reservation(
        self, deal_id: str, offer: Offer, decision: Decision, blockchain_identifier: str | None, human_approved: bool
    ) -> None:
        now = self._timestamp(self._now())
        self._conn.execute(
            "INSERT INTO deals (deal_id, seller_id, amount, unit, status, blockchain_identifier,"
            " human_approved, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                deal_id,
                offer.seller.seller_id,
                offer.price.amount,
                offer.price.unit.value,
                DealStatus.RESERVED.value,
                blockchain_identifier,
                int(human_approved),
                now,
                now,
            ),
        )
        for doc_hash in decision.payable_doc_hashes:
            # A document freed by a refund or a release may be taken over; a held one never.
            cursor = self._conn.execute(
                "INSERT INTO paid_documents (doc_hash, deal_id, status) VALUES (?, ?, ?)"
                " ON CONFLICT (doc_hash) DO UPDATE SET deal_id = excluded.deal_id, status = excluded.status"
                " WHERE paid_documents.status NOT IN (?, ?)",
                (doc_hash, deal_id, DealStatus.RESERVED.value, *_HELD),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"document {doc_hash} is held by another deal")

    # --- outcomes ---

    def mark_paid(self, deal_id: str) -> None:
        """Work verified: these documents are settled and will never be paid again."""
        self._transition(deal_id, {DealStatus.RESERVED}, DealStatus.PAID)

    def mark_refunded(self, deal_id: str) -> None:
        """The money came back (RefundWithdrawn): the documents may go to another seller."""
        self._transition(deal_id, {DealStatus.RESERVED, DealStatus.PAID}, DealStatus.REFUNDED)

    def release(self, deal_id: str) -> None:
        """The purchase never locked any funds. Only call it when that is certain."""
        self._transition(deal_id, {DealStatus.RESERVED}, DealStatus.RELEASED)

    def _transition(self, deal_id: str, allowed: set[DealStatus], target: DealStatus) -> None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute("SELECT status FROM deals WHERE deal_id = ?", (deal_id,)).fetchone()
                if row is None:
                    raise KeyError(f"unknown deal {deal_id}")
                current = DealStatus(row[0])
                if current != target:  # repeating a transition is a no-op
                    if current not in allowed:
                        raise ValueError(f"deal {deal_id} is {current.value}, it cannot become {target.value}")
                    self._conn.execute(
                        "UPDATE deals SET status = ?, updated_at = ? WHERE deal_id = ?",
                        (target.value, self._timestamp(self._now()), deal_id),
                    )
                    self._conn.execute(
                        "UPDATE paid_documents SET status = ? WHERE deal_id = ?", (target.value, deal_id)
                    )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    # --- read side ---

    def deal_status(self, deal_id: str) -> DealStatus | None:
        with self._lock:
            row = self._conn.execute("SELECT status FROM deals WHERE deal_id = ?", (deal_id,)).fetchone()
        return DealStatus(row[0]) if row else None

    def spent_this_month(self) -> int:
        """Reserved plus paid in the current UTC calendar month, in `unit`."""
        with self._lock:
            return self._spent_this_month()

    def _spent_this_month(self) -> int:
        month_start = self._now().astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        (total,) = self._conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM deals"
            " WHERE unit = ? AND status IN (?, ?) AND created_at >= ?",
            (self.unit.value, *_HELD, self._timestamp(month_start)),
        ).fetchone()
        return total

    def _held(self, doc_hashes: Sequence[str]) -> set[str]:
        unique = list(dict.fromkeys(doc_hashes))
        marks = ", ".join("?" * len(unique))
        rows = self._conn.execute(
            f"SELECT doc_hash FROM paid_documents WHERE status IN (?, ?) AND doc_hash IN ({marks})",
            (*_HELD, *unique),
        ).fetchall()
        return {row[0] for row in rows}

    def _money(self, amount: int) -> str:
        return str(Price(amount=amount, unit=self.unit)) if amount >= 0 else f"{amount} {self.unit.value}"

    @staticmethod
    def _timestamp(moment: datetime) -> str:
        # Fixed width in UTC, so comparing the strings compares the moments.
        return moment.astimezone(UTC).isoformat(timespec="microseconds")

    def close(self) -> None:
        self._conn.close()
