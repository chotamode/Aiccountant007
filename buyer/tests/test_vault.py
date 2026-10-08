"""B1: hashes of data/ are stable, 07 is a byte copy of 01, file order does not matter."""

from __future__ import annotations

import hashlib

from buyer.tests.conftest import INVOICES
from buyer.vault import build_job_input, load_documents, manifest
from common.documents import DocumentFormat
from common.hashing import masumi_input_hash


def test_loads_isdoc_and_pdf_sorted_by_name():
    docs = load_documents(INVOICES)
    assert [d.filename for d in docs] == sorted(d.filename for d in docs)
    assert len(docs) == 13
    assert {d.format for d in load_documents(INVOICES, "*.isdoc")} == {DocumentFormat.ISDOC}
    assert len(load_documents(INVOICES, "*.isdoc")) == 8
    assert len(load_documents(INVOICES, "*.pdf")) == 5


def test_hashes_are_stable_between_runs():
    first, second = load_documents(INVOICES), load_documents(INVOICES)
    assert manifest(first) == manifest(second)
    assert build_job_input(first).package_sha256 == build_job_input(second).package_sha256
    for entry in manifest(first):
        raw = (INVOICES / entry.filename).read_bytes()
        assert entry.doc_hash == hashlib.sha256(raw).hexdigest()
        assert entry.size_bytes == len(raw)


def test_duplicate_has_the_hash_of_its_original():
    by_name = {e.filename: e.doc_hash for e in manifest(load_documents(INVOICES, "*.isdoc"))}
    assert by_name["07_duplicate.isdoc"] == by_name["01_tchibo_kava.isdoc"]
    assert len(set(by_name.values())) == 7


def test_file_order_does_not_change_package_hash():
    docs = load_documents(INVOICES, "*.isdoc")
    job, reordered = build_job_input(docs), build_job_input(docs[::-1])
    assert job.package_sha256 == reordered.package_sha256
    # inputHash covers documents_json as sent, so input_data must travel unchanged.
    purchaser_id = "ab" * 8
    assert masumi_input_hash(job.to_input_data(), purchaser_id) != masumi_input_hash(
        reordered.to_input_data(), purchaser_id
    )


def test_skips_files_that_are_not_documents(tmp_path):
    (tmp_path / "README.md").write_text("not a document")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "a.isdoc").write_bytes(b"<Invoice/>")
    assert [d.filename for d in load_documents(tmp_path)] == ["a.isdoc", "b.pdf"]
