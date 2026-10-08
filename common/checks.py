"""Buyer-side verification of the seller's work."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

import canonicaljson
from pydantic import BaseModel, Field

from common.hashing import sha256_hex


class CheckCode(StrEnum):
    DOC_HASH_MATCH = "doc_hash_match"  # seller's doc_hash equals our sha256 of the file
    READABLE = "readable"  # status == ok
    LINES_SUM = "lines_sum"  # sum(qty * unit_price) == total_without_vat
    VAT_RATE_ALLOWED = "vat_rate_allowed"  # every line rate in CZ_VAT_RATES
    VAT_AMOUNT = "vat_amount"  # vat_amount == sum(line * rate), rounded
    TOTAL = "total"  # total == total_without_vat + vat_amount
    MATCHES_SOURCE = "matches_source"  # optional: values equal the original ISDOC
    ICO_ARES = "ico_ares"  # IČO exists in ARES and the name matches
    DIC_FORMAT = "dic_format"
    DUPLICATE = "duplicate"  # same doc_hash / supplier+number already seen
    PROMPT_INJECTION = "prompt_injection"  # document text tries to instruct the agent


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"  # blocks payment, triggers refund


class Check(BaseModel):
    code: CheckCode
    passed: bool
    severity: Severity = Severity.ERROR
    doc_hash: str | None = None  # None = check on the whole package
    message: str
    expected: str | None = None
    actual: str | None = None
    simulated: bool = False  # e.g. ARES unreachable and a cached/mock answer was used


class VerificationReport(BaseModel):
    """Evidence attached to a refund request and shown on the dashboard."""

    seller_id: str
    package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    blockchain_identifier: str | None = None
    checks: list[Check]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def blocking_failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed and c.severity == Severity.ERROR]

    @property
    def passed(self) -> bool:
        return not self.blocking_failures

    @property
    def failed_doc_hashes(self) -> set[str]:
        return {c.doc_hash for c in self.blocking_failures if c.doc_hash}

    def report_hash(self) -> str:
        """Stable hash of the report, logged with the refund request."""
        payload = self.model_dump(mode="json")
        return sha256_hex(canonicaljson.encode_canonical_json(payload))
