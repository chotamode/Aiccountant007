"""The two accounting firms behind FIRM_PROFILE: honest and sloppy."""

from __future__ import annotations

import os
from decimal import Decimal

from pydantic import BaseModel

from common.invoice import ExtractedInvoice, ExtractionStatus

SLOPPY_FROM_RATE = Decimal(21)
SLOPPY_TO_RATE = Decimal(15)
SLOPPY_DOC_COUNT = 2
CENT = Decimal("0.01")


class FirmProfile(BaseModel):
    key: str  # FIRM_PROFILE value
    name: str  # seller_name in JobResult and Ledger
    price_lovelace: int  # fixed at Masumi registration
    sloppy: bool = False


HONEST = FirmProfile(key="honest", name="ProÚčetní", price_lovelace=5_000_000)
SLOPPY = FirmProfile(key="sloppy", name="CheapBooks", price_lovelace=2_000_000, sloppy=True)
PROFILES: dict[str, FirmProfile] = {p.key: p for p in (HONEST, SLOPPY)}


def load_profile(key: str | None = None) -> FirmProfile:
    """Profile from FIRM_PROFILE; FIRM_PRICE_LOVELACE overrides the price."""
    key = key or os.environ.get("FIRM_PROFILE", "honest")
    try:
        profile = PROFILES[key]
    except KeyError:
        raise ValueError(f"unknown FIRM_PROFILE {key!r}, expected one of {sorted(PROFILES)}") from None
    price = os.environ.get("FIRM_PRICE_LOVELACE")
    return profile.model_copy(update={"price_lovelace": int(price)}) if price else profile


def _has_basic_rate(invoice: ExtractedInvoice) -> bool:
    return invoice.status == ExtractionStatus.OK and any(
        line.vat_rate == SLOPPY_FROM_RATE for line in invoice.lines
    )


def _downgrade_vat(invoice: ExtractedInvoice) -> ExtractedInvoice:
    """21% lines become 15%, VAT and total shift by the same amount.

    total_without_vat stays, so the document still adds up internally and
    only a rate check against CZ_VAT_RATES (or the source ISDOC) exposes it.
    """
    lines, shifted_base = [], Decimal(0)
    for line in invoice.lines:
        if line.vat_rate == SLOPPY_FROM_RATE:
            shifted_base += line.total_without_vat
            line = line.model_copy(update={"vat_rate": SLOPPY_TO_RATE})
        lines.append(line)
    delta = (shifted_base * (SLOPPY_FROM_RATE - SLOPPY_TO_RATE) / 100).quantize(CENT)
    update: dict[str, object] = {"lines": lines}
    if invoice.vat_amount is not None:
        update["vat_amount"] = invoice.vat_amount - delta
    if invoice.total is not None:
        update["total"] = invoice.total - delta
    return invoice.model_copy(update=update)


def apply_profile(invoices: list[ExtractedInvoice], profile: FirmProfile) -> list[ExtractedInvoice]:
    """Honest returns the input; sloppy corrupts DPH in a fixed set of documents.

    The victims are the first SLOPPY_DOC_COUNT readable documents, ordered by
    filename, that have a 21% line. No randomness: every run hits the same files.
    """
    if not profile.sloppy:
        return invoices
    candidates = sorted(
        (i for i, inv in enumerate(invoices) if _has_basic_rate(inv)),
        key=lambda i: (invoices[i].filename or "", i),
    )
    victims = set(candidates[:SLOPPY_DOC_COUNT])
    return [_downgrade_vat(inv) if i in victims else inv for i, inv in enumerate(invoices)]
