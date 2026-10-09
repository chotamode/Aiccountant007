import tempfile
from pathlib import Path

import pytest

from buyer.vault import load_documents
from buyer.verifier import AresClient, AresResult, HttpAresClient, verify
from common.checks import CheckCode, Severity
from common.mip003 import JobInput
from seller.processing import process
from seller.profiles import HONEST, SLOPPY

DATA_DIR = Path("data/invoices")


class MockAres:
    def __init__(self, invalid_icos: set[str] | None = None) -> None:
        self.invalid_icos = invalid_icos or {"98765418"}

    def lookup(self, ico: str) -> AresResult:
        if ico in self.invalid_icos:
            return AresResult(ico=ico, name=None, exists=False, simulated=True)
        return AresResult(ico=ico, name="Mock Supplier s.r.o.", exists=True, simulated=True)


@pytest.fixture
def ares() -> AresClient:
    return MockAres()


def test_honest_passes_on_01_to_05(ares: AresClient):
    docs = load_documents(DATA_DIR, "0[1-5]*.isdoc")
    assert len(docs) == 5

    job_input = JobInput.build(docs)
    honest_res, _ = process(job_input, HONEST)

    report = verify(job_input, honest_res, ares, seller_id="ProÚčetní")
    assert report.passed
    assert len(report.blocking_failures) == 0
    assert len(report.failed_doc_hashes) == 0


def test_sloppy_fails_exactly_two_on_01_to_05(ares: AresClient):
    docs = load_documents(DATA_DIR, "0[1-5]*.isdoc")
    assert len(docs) == 5

    job_input = JobInput.build(docs)
    sloppy_res, _ = process(job_input, SLOPPY)

    report = verify(job_input, sloppy_res, ares, seller_id="CheapBooks")
    assert not report.passed
    assert len(report.failed_doc_hashes) == 2


def test_supplier_vat_error_06_is_warning_not_blocking(ares: AresClient):
    docs = load_documents(DATA_DIR, "06*.isdoc")
    assert len(docs) == 1

    job_input = JobInput.build(docs)
    honest_res, _ = process(job_input, HONEST)

    report = verify(job_input, honest_res, ares, seller_id="ProÚčetní")
    # Must not block payment (supplier error in source, not seller's fault)
    assert report.passed
    assert len(report.blocking_failures) == 0

    vat_checks = [c for c in report.checks if c.code == CheckCode.VAT_AMOUNT]
    assert len(vat_checks) == 1
    assert vat_checks[0].severity == Severity.WARNING


def test_injection_found_in_08(ares: AresClient):
    docs = load_documents(DATA_DIR, "08*.isdoc")
    assert len(docs) == 1

    job_input = JobInput.build(docs)
    honest_res, _ = process(job_input, HONEST)

    report = verify(job_input, honest_res, ares, seller_id="ProÚčetní")
    injection_checks = [c for c in report.checks if c.code == CheckCode.PROMPT_INJECTION]
    assert len(injection_checks) == 1
    assert not injection_checks[0].passed
    assert injection_checks[0].severity == Severity.WARNING
    assert "pay 10x" in (injection_checks[0].actual or "").lower() or "ignore" in (injection_checks[0].actual or "").lower()


def test_http_ares_client_cache():
    with tempfile.TemporaryDirectory() as tmp:
        cache_file = Path(tmp) / "ares.json"
        client = HttpAresClient(cache_path=cache_file, timeout=1.0)
        # Seed cache manually
        client._cache["12345678"] = {"ico": "12345678", "name": "Cached Corp", "exists": True, "simulated": False}
        res = client.lookup("12345678")
        assert res.name == "Cached Corp"
        assert res.exists
