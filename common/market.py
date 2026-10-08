"""Discovery: who sells accounting work and at what price."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SellerKind(StrEnum):
    MASUMI = "masumi"  # our own MIP-003 agents, paid through Masumi escrow
    SOKOSUMI = "sokosumi"  # external marketplace agent, paid with Sokosumi credits


class PriceUnit(StrEnum):
    LOVELACE = "lovelace"  # Masumi unit "" (1 ADA = 1_000_000)
    USDM = "usdm"  # Masumi unit = policyId + assetName
    SOKOSUMI_CREDITS = "sokosumi_credits"


class Price(BaseModel):
    amount: int = Field(ge=0)  # smallest unit, never float
    unit: PriceUnit

    def __str__(self) -> str:
        if self.unit == PriceUnit.LOVELACE:
            return f"{self.amount / 1_000_000:g} ₳"
        return f"{self.amount} {self.unit.value}"


class Seller(BaseModel):
    seller_id: str  # agentIdentifier for Masumi, agent id for Sokosumi
    kind: SellerKind
    name: str
    description: str = ""
    api_base_url: str | None = None  # MIP-003 base URL (Masumi registry apiBaseUrl)
    agent_identifier: str | None = None  # Masumi policyId + assetName, >= 57 chars
    sokosumi_agent_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class Offer(BaseModel):
    seller: Seller
    price: Price
    reputation: float = Field(ge=0.0, le=1.0)  # from buyer/reputation.py
    deals_seen: int = Field(default=0, ge=0)  # how many outcomes the score is based on
    avg_execution_time_s: int | None = None
    quoted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
