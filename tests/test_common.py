"""Contract tests: both agents rely on these invariants."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from common import (
    Actor,
    Check,
    CheckCode,
    Document,
    Event,
    EventType,
    ExtractedInvoice,
    ExtractionStatus,
    InvoiceLine,
    JobInput,
    JobResult,
    StartJobResponse,
    VerificationReport,
    new_purchaser_id,
)
from common.hashing import masumi_input_hash, package_hash

ISDOC = b"<Invoice><ID>2026-001</ID></Invoice>"


def test_package_hash_is_order_independent_and_counts_duplicates() -> None:
    a = Document.from_bytes("a.isdoc", ISDOC)
    b = Document.from_bytes("b.isdoc", b"<Invoice><ID>2026-002</ID></Invoice>")
    assert JobInput.build([a, b]).package_sha256 == JobInput.build([b, a]).package_sha256
    assert package_hash([a.doc_hash]) != package_hash([a.doc_hash, a.doc_hash])


def test_job_input_roundtrip_keeps_masumi_input_hash() -> None:
    job = JobInput.build([Document.from_bytes("a.isdoc", ISDOC)])
    input_data = job.to_input_data()
    assert all(isinstance(v, str) for v in input_data.values())
    restored = JobInput.from_input_data(input_data)
    pid = new_purchaser_id()
    assert masumi_input_hash(restored.to_input_data(), pid) == masumi_input_hash(input_data, pid)


def test_tampered_package_is_rejected() -> None:
    input_data = JobInput.build([Document.from_bytes("a.isdoc", ISDOC)]).to_input_data()
    input_data["package_sha256"] = "0" * 64
    with pytest.raises(ValidationError):
        JobInput.from_input_data(input_data)


def test_purchaser_id_fits_masumi_constraints() -> None:
    pid = new_purchaser_id()
    assert 14 <= len(pid) <= 26
    int(pid, 16)


def test_job_result_roundtrip_with_wrong_vat_rate() -> None:
    doc = Document.from_bytes("a.isdoc", ISDOC)
    invoice = ExtractedInvoice(
        doc_hash=doc.doc_hash,
        status=ExtractionStatus.OK,
        lines=[InvoiceLine(desc="Káva", qty=Decimal(2), unit_price=Decimal("50.00"), vat_rate=Decimal(15))],
        total_without_vat=Decimal("100.00"),
        vat_amount=Decimal("15.00"),
        total=Decimal("115.00"),
    )
    result = JobResult(seller_name="CheapBooks", package_sha256=package_hash([doc.doc_hash]), invoices=[invoice])
    restored = JobResult.from_result_string(result.to_result_string())
    assert restored.invoices[0].lines[0].vat_rate == Decimal(15)
    assert restored.invoices[0].total == Decimal("115.00")


def test_start_job_response_accepts_template_shape() -> None:
    raw = {
        "status": "success",
        "job_id": "j1",
        "blockchainIdentifier": "bc",
        "agentIdentifier": "a" * 57,
        "sellerVKey": "vk",
        "identifierFromPurchaser": "abcdef0123456789",
        "input_hash": "f" * 64,
        "payByTime": 1,
        "submitResultTime": "2",
        "unlockTime": "3",
        "externalDisputeUnlockTime": "4",
    }
    parsed = StartJobResponse.model_validate(raw)
    assert parsed.pay_by_time == "1"
    assert parsed.blockchain_identifier == "bc"


def test_report_passes_only_without_blocking_failures() -> None:
    ok = Check(code=CheckCode.TOTAL, passed=True, message="ok")
    bad = Check(code=CheckCode.VAT_RATE_ALLOWED, passed=False, doc_hash="a" * 64, message="15% is not a CZ rate")
    assert VerificationReport(seller_id="s", package_sha256="b" * 64, checks=[ok]).passed
    report = VerificationReport(seller_id="s", package_sha256="b" * 64, checks=[ok, bad])
    assert not report.passed
    assert report.failed_doc_hashes == {"a" * 64}
    assert len(report.report_hash()) == 64


def test_event_sse_format() -> None:
    event = Event(actor=Actor.BUYER, type=EventType.ESCROW_LOCKED, msg="2 ₳ заблокировано")
    sse = event.to_sse()
    assert sse.startswith("event: escrow_locked\ndata: {")
    assert sse.endswith("\n\n")
