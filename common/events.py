"""Event feed shared by buyer, seller and the dashboard (SSE)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Actor(StrEnum):
    BUYER = "buyer"
    SELLER = "seller"
    SYSTEM = "system"


class EventType(StrEnum):
    # discovery
    DISCOVERY_STARTED = "discovery_started"
    OFFER_FOUND = "offer_found"
    SELLER_SELECTED = "seller_selected"
    # hand-over
    DOCS_HASHED = "docs_hashed"
    JOB_STARTED = "job_started"
    # wallet policy
    POLICY_APPROVED = "policy_approved"
    POLICY_BLOCKED = "policy_blocked"  # limit / per-task max / injection
    DUPLICATE_BLOCKED = "duplicate_blocked"  # idempotency: never pay twice
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    HUMAN_APPROVED = "human_approved"
    # escrow (Masumi on-chain states)
    ESCROW_LOCKED = "escrow_locked"  # FundsLocked
    RESULT_SUBMITTED = "result_submitted"  # ResultSubmitted
    PAYMENT_RELEASED = "payment_released"  # Withdrawn by seller after unlockTime
    REFUND_REQUESTED = "refund_requested"  # RefundRequested / Disputed
    REFUND_AUTHORIZED = "refund_authorized"  # seller authorize-refund
    REFUND_WITHDRAWN = "refund_withdrawn"  # RefundWithdrawn
    # seller work
    OCR_PAID = "ocr_paid"  # expensive action paid by the seller
    JOB_COMPLETED = "job_completed"
    # verification
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    REPUTATION_UPDATED = "reputation_updated"
    ERROR = "error"


class Event(BaseModel):
    """Example: {"ts": "...", "actor": "buyer", "type": "escrow_locked",
    "msg": "2 ₳ заблокировано", "tx_url": "...", "simulated": false}"""

    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: Actor
    type: EventType
    msg: str
    tx_url: str | None = None  # e.g. https://preprod.cardanoscan.io/transaction/<hash>
    simulated: bool = False  # anything not on testnet/sandbox/mainnet MUST be True
    deal_id: str | None = None  # groups events of one purchase
    data: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        return f"event: {self.type}\ndata: {self.model_dump_json()}\n\n"
