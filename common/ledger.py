"""Seller P&L, exposed on GET /ledger."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class LedgerKind(StrEnum):
    REVENUE = "revenue"  # escrow amount for a job
    COST = "cost"  # OCR (Apify) or LLM spend for a job


class LedgerEntry(BaseModel):
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    job_id: str
    kind: LedgerKind
    amount: Decimal = Field(ge=0)
    unit: str  # "ADA", "USD", ...
    description: str
    simulated: bool = False


class Ledger(BaseModel):
    seller_name: str
    entries: list[LedgerEntry] = Field(default_factory=list)

    def totals(self, kind: LedgerKind) -> dict[str, Decimal]:
        result: dict[str, Decimal] = {}
        for entry in self.entries:
            if entry.kind == kind:
                result[entry.unit] = result.get(entry.unit, Decimal(0)) + entry.amount
        return result
