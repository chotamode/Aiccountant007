"""Seller output: one extracted invoice per input document."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

# Valid Czech DPH rates in percent (since 2024: 21 basic, 12 reduced, 0 exempt).
CZ_VAT_RATES: frozenset[Decimal] = frozenset({Decimal(0), Decimal(12), Decimal(21)})


class ExtractionStatus(StrEnum):
    OK = "ok"
    UNREADABLE = "unreadable"


class InvoiceLine(BaseModel):
    desc: str
    qty: Decimal
    unit_price: Decimal  # without VAT, in invoice currency
    vat_rate: Decimal  # percent, e.g. 21; any value accepted here, the verifier judges it

    @property
    def total_without_vat(self) -> Decimal:
        return self.qty * self.unit_price


class ExtractedInvoice(BaseModel):
    """Fields from CONTEXT section 6, plus `filename` for the dashboard.

    Deliberately lenient: a sloppy seller must still produce a parseable
    result, so wrong values are caught by the buyer's verifier, not here.
    Money is Decimal and serializes to JSON strings (stable hashing).
    """

    doc_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    filename: str | None = None
    status: ExtractionStatus
    supplier_name: str | None = None
    ico: str | None = None  # IČO, 8 digits
    dic: str | None = None  # DIČ, "CZ" + 8-10 digits
    invoice_number: str | None = None
    issue_date: date | None = None
    currency: str = Field(default="CZK", min_length=3, max_length=3)
    lines: list[InvoiceLine] = Field(default_factory=list)
    total_without_vat: Decimal | None = None
    vat_amount: Decimal | None = None
    total: Decimal | None = None
    bank_account: str | None = None
