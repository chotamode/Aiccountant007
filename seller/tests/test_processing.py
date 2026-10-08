"""V1 criteria 2-3 on the mini fixtures, always runnable without data/."""

from __future__ import annotations

from decimal import Decimal

from common.invoice import ExtractionStatus
from common.isdoc import parse_isdoc
from common.mip003 import JobInput
from seller.processing import process
from seller.profiles import HONEST, SLOPPY, load_profile


def test_parse_isdoc_reads_all_fields(fixture_documents):
    doc = fixture_documents[0]
    inv = parse_isdoc(doc.content, filename=doc.filename)
    assert inv.status == ExtractionStatus.OK
    assert inv.doc_hash == doc.doc_hash
    assert (inv.invoice_number, inv.ico, inv.dic) == ("FV-0001", "45274649", "CZ45274649")
    assert inv.supplier_name == "ČEZ, a. s."
    assert str(inv.issue_date) == "2026-09-01"
    assert inv.bank_account == "123456789/0800"
    assert [line.vat_rate for line in inv.lines] == [Decimal(21), Decimal(12)]
    assert (inv.total_without_vat, inv.vat_amount, inv.total) == (
        Decimal("1200.00"), Decimal("234.00"), Decimal("1434.00"))


def test_parse_isdoc_never_raises():
    assert parse_isdoc(b"<not xml").status == ExtractionStatus.UNREADABLE
    assert parse_isdoc(b"<Other/>").status == ExtractionStatus.UNREADABLE
    bomb = b'<!DOCTYPE x [<!ENTITY a "aaaa">]><Invoice>&a;</Invoice>'
    assert parse_isdoc(bomb).status == ExtractionStatus.UNREADABLE


def test_honest_is_plain_extraction(fixture_documents):
    result, costs = process(JobInput.build(fixture_documents), HONEST)
    assert result.seller_name == "ProÚčetní"
    assert result.invoices == [parse_isdoc(d.content, d.filename) for d in fixture_documents]
    assert all(c.amount == 0 for c in costs)


def test_sloppy_corrupts_exactly_two_documents(fixture_documents):
    job = JobInput.build(list(reversed(fixture_documents)))  # order of input must not matter
    honest, _ = process(job, HONEST)
    sloppy, _ = process(job, SLOPPY)
    changed = sorted(h.filename for h, s in zip(honest.invoices, sloppy.invoices) if h != s)
    assert changed == ["a_mini.isdoc", "b_mini.isdoc"]
    for h, s in zip(honest.invoices, sloppy.invoices):
        if h == s:
            continue
        diff = {k for k in type(h).model_fields if getattr(h, k) != getattr(s, k)}
        assert diff == {"lines", "vat_amount", "total"}
        assert [line.vat_rate for line in s.lines] == [Decimal(15), Decimal(12)]
        assert s.total == s.total_without_vat + s.vat_amount  # still adds up
        assert s.vat_amount == h.vat_amount - Decimal("60.00")


def test_pdf_is_unreadable_until_ocr(fixture_documents):
    from common.documents import Document

    job = JobInput.build([*fixture_documents, Document.from_bytes("01.pdf", b"%PDF-1.4")])
    result, _ = process(job, HONEST)
    assert result.invoices[-1].status == ExtractionStatus.UNREADABLE


def test_load_profile_env(monkeypatch):
    monkeypatch.setenv("FIRM_PROFILE", "sloppy")
    monkeypatch.setenv("FIRM_PRICE_LOVELACE", "1234")
    profile = load_profile()
    assert (profile.name, profile.price_lovelace, profile.sloppy) == ("CheapBooks", 1234, True)


def _variant(fixture_documents, old: str, new: str, encoding: str = "utf-8") -> bytes:
    return fixture_documents[0].content.decode("utf-8").replace(old, new).encode(encoding)


def test_parse_isdoc_variants(fixture_documents):
    isdoc5 = _variant(fixture_documents, "namespace/2013", "namespace/invoice")
    no_ns = _variant(fixture_documents, ' xmlns="http://isdoc.cz/namespace/2013"', "")
    bom = b"\xef\xbb\xbf" + fixture_documents[0].content
    for content in (isdoc5, no_ns, bom):
        assert parse_isdoc(content).total == Decimal("1434.00")
    cp1250 = _variant(fixture_documents, 'encoding="UTF-8"', 'encoding="windows-1250"', "cp1250")
    assert parse_isdoc(cp1250).supplier_name == "ČEZ, a. s."
    iban = _variant(fixture_documents, "<ID>123456789</ID><BankCode>0800</BankCode>",
                    "<IBAN>CZ65 0800 0000 1920 0014 5399</IBAN>")
    assert parse_isdoc(iban).bank_account == "CZ6508000000192000145399"


def test_sloppy_skips_byte_duplicates_by_filename_order(fixture_documents):
    from common.documents import Document

    a, b, _ = fixture_documents
    docs = [Document.from_bytes("07_duplicate.isdoc", a.content), b, a]
    sloppy, _ = process(JobInput.build(docs), SLOPPY)
    corrupted = sorted(i.filename for i in sloppy.invoices if i.lines[0].vat_rate == 15)
    # Order is by filename, not by content: "07_…" sorts before "a_…".
    assert corrupted == ["07_duplicate.isdoc", "a_mini.isdoc"]
