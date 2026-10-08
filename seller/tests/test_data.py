"""V1 criteria 2-3 against data/ (N1). Skipped until data/expected.json exists."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from common.invoice import ExtractedInvoice
from common.mip003 import JobInput
from seller.processing import process
from seller.profiles import HONEST, SLOPPY
from seller.tests.conftest import DATA, documents_from

EXPECTED = DATA / "expected.json"
pytestmark = pytest.mark.skipif(not EXPECTED.exists(), reason="data/expected.json not there yet (N1)")

FIELDS = ("invoice_number", "ico", "dic", "supplier_name", "issue_date", "currency",
          "total_without_vat", "vat_amount", "total", "bank_account")
MONEY = {"total_without_vat", "vat_amount", "total", "qty", "unit_price", "vat_rate"}


def _norm(key: str, value: Any) -> Any:
    if value is None:
        return None
    return Decimal(str(value)).normalize() if key in MONEY else str(value)


def _expected() -> dict[str, dict[str, Any]]:
    raw = json.loads(EXPECTED.read_text())
    if isinstance(raw, list):
        return {item["filename"]: item for item in raw}
    return raw.get("documents", raw) if isinstance(raw, dict) else {}


def _as_expected(inv: ExtractedInvoice) -> dict[str, Any]:
    data = inv.model_dump(mode="json")
    out = {k: _norm(k, data[k]) for k in FIELDS}
    out["lines"] = [{k: _norm(k, v) for k, v in line.items()} for line in data["lines"]]
    return out


def _truth(entry: dict[str, Any]) -> dict[str, Any]:
    out = {k: _norm(k, entry.get(k)) for k in FIELDS}
    out["lines"] = [{k: _norm(k, line.get(k)) for k in ("desc", "qty", "unit_price", "vat_rate")}
                    for line in entry.get("lines", [])]
    return out


@pytest.fixture(scope="module")
def normal_docs():
    paths = sorted((DATA / "invoices").glob("0[1-5]*.isdoc"))
    assert paths, "data/invoices/0[1-5]*.isdoc missing"
    return documents_from(paths)


def test_honest_matches_expected(normal_docs):
    expected = _expected()
    result, _ = process(JobInput.build(normal_docs), HONEST)
    for inv in result.invoices:
        assert _as_expected(inv) == _truth(expected[inv.filename]), inv.filename


def test_sloppy_differs_in_exactly_two(normal_docs):
    expected = _expected()
    result, _ = process(JobInput.build(normal_docs), SLOPPY)
    wrong = {}
    for inv in result.invoices:
        got, truth = _as_expected(inv), _truth(expected[inv.filename])
        diff = {k for k in got if got[k] != truth[k]}
        if diff:
            wrong[inv.filename] = diff
    assert len(wrong) == 2, wrong
    assert all(d <= {"lines", "vat_amount", "total"} for d in wrong.values()), wrong
