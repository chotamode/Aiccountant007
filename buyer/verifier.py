"""Buyer-side verifier: independent verification of the seller's extraction work (task B5).

The buyer never trusts the seller's output blindly. For every invoice delivered,
the verifier checks:
- Document hash matches the input document (DOC_HASH_MATCH)
- Document was extracted successfully (READABLE)
- Line arithmetic: sum of lines == total_without_vat (LINES_SUM)
- Allowed Czech VAT rates: 0%, 12%, 21% (VAT_RATE_ALLOWED)
- VAT calculation: vat_amount == sum(line * rate) (VAT_AMOUNT)
- Grand total: total_without_vat + vat_amount == total (TOTAL)
- Match against source ISDOC ground truth (MATCHES_SOURCE)
- Company verification in ARES (ICO_ARES)
- DIČ format check (DIC_FORMAT)
- Duplicates in package (DUPLICATE)
- Prompt injection detection in document text (PROMPT_INJECTION)

Errors (Severity.ERROR) block payment and trigger a refund.
Warnings (Severity.WARNING), such as supplier errors already present in the original invoice,
do not penalize the seller.
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from common.checks import Check, CheckCode, Severity, VerificationReport
from common.invoice import CZ_VAT_RATES, ExtractedInvoice, ExtractionStatus
from common.isdoc import parse_isdoc
from common.mip003 import JobInput, JobResult

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"pay\s+10x", re.IGNORECASE),
    re.compile(r"zapla[tť]\s+10x", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"authorized\s+by\s+the\s+client", re.IGNORECASE),
]

DIC_PATTERN = re.compile(r"^CZ\d{8,10}$")


class AresResult(BaseModel):
    ico: str
    name: str | None = None
    exists: bool = True
    simulated: bool = False


class AresClient(Protocol):
    def lookup(self, ico: str) -> AresResult: ...


class HttpAresClient:
    """ARES economic subjects lookup with disk cache and simulation fallback."""

    def __init__(self, cache_path: Path | None = None, timeout: float = 5.0) -> None:
        self.cache_path = Path(cache_path) if cache_path else None
        self.timeout = timeout
        self._cache: dict[str, dict[str, Any]] = {}
        if self.cache_path and self.cache_path.exists():
            try:
                self._cache = json.loads(self.cache_path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def lookup(self, ico: str) -> AresResult:
        ico = ico.strip()
        if ico in self._cache:
            return AresResult.model_validate(self._cache[ico])
        try:
            resp = httpx.get(
                f"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}",
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                body = resp.json()
                name = body.get("obchodniJmeno")
                res = AresResult(ico=ico, name=name, exists=True, simulated=False)
            elif resp.status_code == 404:
                res = AresResult(ico=ico, name=None, exists=False, simulated=False)
            else:
                res = AresResult(ico=ico, exists=True, simulated=True)
        except (httpx.HTTPError, ValueError):
            res = AresResult(ico=ico, exists=True, simulated=True)

        self._cache[ico] = res.model_dump()
        self._save_cache()
        return res

    def _save_cache(self) -> None:
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=2, ensure_ascii=False), "utf-8")


def _find_injection(text: str) -> str | None:
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def verify(
    job_input: JobInput,
    job_result: JobResult,
    ares: AresClient,
    seller_id: str = "",
    blockchain_identifier: str | None = None,
) -> VerificationReport:
    """Verify extracted invoices against input documents and accounting rules."""
    checks: list[Check] = []
    invoices_by_hash = {inv.doc_hash: inv for inv in job_result.invoices}

    seen_hashes: set[str] = set()
    seen_invoices: set[tuple[str, str]] = set()

    for doc in job_input.documents:
        inv = invoices_by_hash.get(doc.doc_hash)
        if inv is None:
            # Fallback by filename if seller returned wrong doc_hash
            inv = next((i for i in job_result.invoices if i.filename == doc.filename), None)

        if inv is None:
            checks.append(
                Check(
                    code=CheckCode.DOC_HASH_MATCH,
                    passed=False,
                    severity=Severity.ERROR,
                    doc_hash=doc.doc_hash,
                    message=f"Missing extraction result for {doc.filename}",
                )
            )
            continue

        # 1. DOC_HASH_MATCH
        hash_match = inv.doc_hash == doc.doc_hash
        checks.append(
            Check(
                code=CheckCode.DOC_HASH_MATCH,
                passed=hash_match,
                severity=Severity.ERROR if not hash_match else Severity.INFO,
                doc_hash=doc.doc_hash,
                expected=doc.doc_hash,
                actual=inv.doc_hash,
                message=f"Doc hash matches {doc.filename}" if hash_match else f"Doc hash mismatch in {doc.filename}",
            )
        )

        # 2. READABLE
        readable = inv.status == ExtractionStatus.OK
        checks.append(
            Check(
                code=CheckCode.READABLE,
                passed=readable,
                severity=Severity.ERROR if not readable else Severity.INFO,
                doc_hash=doc.doc_hash,
                message=f"{doc.filename} extraction readable" if readable else f"{doc.filename} unreadable",
            )
        )
        if not readable:
            continue

        # Ground truth parse of source ISDOC (if ISDOC)
        source_isdoc: ExtractedInvoice | None = None
        if doc.filename.endswith(".isdoc") or b"<Invoice" in doc.content[:2048]:
            source_isdoc = parse_isdoc(doc.content, doc.filename)

        # 3. PROMPT_INJECTION check
        doc_text = doc.content.decode("utf-8", errors="ignore")
        injection_found = _find_injection(doc_text)
        if not injection_found and inv.lines:
            for line in inv.lines:
                injection_found = _find_injection(line.desc)
                if injection_found:
                    break

        checks.append(
            Check(
                code=CheckCode.PROMPT_INJECTION,
                passed=injection_found is None,
                severity=Severity.WARNING,
                doc_hash=doc.doc_hash,
                actual=injection_found,
                message=(
                    f"Prompt injection detected in {doc.filename}: {injection_found}"
                    if injection_found
                    else f"No prompt injection in {doc.filename}"
                ),
            )
        )

        # 4. DUPLICATE check within package
        is_dup_hash = doc.doc_hash in seen_hashes
        inv_key = (inv.ico or "", inv.invoice_number or "")
        is_dup_number = bool(inv.ico and inv.invoice_number and inv_key in seen_invoices)
        if is_dup_hash or is_dup_number:
            checks.append(
                Check(
                    code=CheckCode.DUPLICATE,
                    passed=False,
                    severity=Severity.WARNING,
                    doc_hash=doc.doc_hash,
                    message=f"Duplicate invoice detected: {doc.filename}",
                )
            )
        seen_hashes.add(doc.doc_hash)
        if inv.ico and inv.invoice_number:
            seen_invoices.add(inv_key)

        # 5. LINES_SUM check: sum(qty * unit_price) == total_without_vat
        calc_lines_sum = sum(line.total_without_vat for line in inv.lines)
        lines_sum_diff = abs(calc_lines_sum - (inv.total_without_vat or Decimal(0)))
        lines_sum_ok = lines_sum_diff <= Decimal("0.05")

        # Check if source ISDOC already had this discrepancy
        source_had_lines_diff = False
        if source_isdoc and source_isdoc.lines:
            source_calc = sum(l.total_without_vat for l in source_isdoc.lines)
            source_had_lines_diff = abs(source_calc - (source_isdoc.total_without_vat or Decimal(0))) > Decimal("0.05")

        checks.append(
            Check(
                code=CheckCode.LINES_SUM,
                passed=lines_sum_ok or source_had_lines_diff,
                severity=Severity.WARNING if source_had_lines_diff else (Severity.INFO if lines_sum_ok else Severity.ERROR),
                doc_hash=doc.doc_hash,
                expected=str(calc_lines_sum),
                actual=str(inv.total_without_vat),
                message=(
                    f"Lines sum matches in {doc.filename}"
                    if lines_sum_ok
                    else (
                        f"Lines sum error in supplier source for {doc.filename}"
                        if source_had_lines_diff
                        else f"Lines sum mismatch in {doc.filename}: sum={calc_lines_sum}, total_without_vat={inv.total_without_vat}"
                    )
                ),
            )
        )

        # 6. VAT_RATE_ALLOWED check
        invalid_rates = [line.vat_rate for line in inv.lines if line.vat_rate not in CZ_VAT_RATES]
        rates_ok = len(invalid_rates) == 0

        source_had_invalid_rates = False
        if source_isdoc:
            source_invalid = [l.vat_rate for l in source_isdoc.lines if l.vat_rate not in CZ_VAT_RATES]
            source_had_invalid_rates = len(source_invalid) > 0

        checks.append(
            Check(
                code=CheckCode.VAT_RATE_ALLOWED,
                passed=rates_ok or source_had_invalid_rates,
                severity=Severity.WARNING if source_had_invalid_rates else (Severity.INFO if rates_ok else Severity.ERROR),
                doc_hash=doc.doc_hash,
                actual=", ".join(str(r) for r in invalid_rates) if invalid_rates else None,
                message=(
                    f"All VAT rates allowed in {doc.filename}"
                    if rates_ok
                    else (
                        f"Supplier used non-standard VAT rate in {doc.filename}"
                        if source_had_invalid_rates
                        else f"Invalid VAT rate(s) {invalid_rates} in {doc.filename}"
                    )
                ),
            )
        )

        # 7. VAT_AMOUNT check: vat_amount == sum(line * rate)
        calc_vat = sum(
            (line.qty * line.unit_price * (line.vat_rate / Decimal(100))).quantize(Decimal("0.01"))
            for line in inv.lines
        )
        vat_diff = abs(calc_vat - (inv.vat_amount or Decimal(0)))
        vat_ok = vat_diff <= Decimal("0.05")

        source_had_vat_err = False
        if source_isdoc and source_isdoc.lines:
            src_vat = sum(
                (l.qty * l.unit_price * (l.vat_rate / Decimal(100))).quantize(Decimal("0.01"))
                for l in source_isdoc.lines
            )
            source_had_vat_err = abs(src_vat - (source_isdoc.vat_amount or Decimal(0))) > Decimal("0.05")

        # Did the seller extract what was in the source document?
        seller_extracted_source_vat = (
            source_isdoc is not None and abs((source_isdoc.vat_amount or Decimal(0)) - (inv.vat_amount or Decimal(0))) <= Decimal("0.05")
        )

        is_supplier_vat_error = source_had_vat_err and seller_extracted_source_vat

        checks.append(
            Check(
                code=CheckCode.VAT_AMOUNT,
                passed=vat_ok or is_supplier_vat_error,
                severity=Severity.WARNING if is_supplier_vat_error else (Severity.INFO if vat_ok else Severity.ERROR),
                doc_hash=doc.doc_hash,
                expected=str(calc_vat),
                actual=str(inv.vat_amount),
                message=(
                    f"VAT amount verified in {doc.filename}"
                    if vat_ok
                    else (
                        f"Supplier VAT error in original document {doc.filename}"
                        if is_supplier_vat_error
                        else f"VAT amount mismatch in {doc.filename}: calc={calc_vat}, invoice={inv.vat_amount}"
                    )
                ),
            )
        )

        # 8. TOTAL check: total_without_vat + vat_amount == total
        calc_total = (inv.total_without_vat or Decimal(0)) + (inv.vat_amount or Decimal(0))
        total_diff = abs(calc_total - (inv.total or Decimal(0)))
        total_ok = total_diff <= Decimal("1.00")  # allow up to 1 CZK for zaokrouhlení

        checks.append(
            Check(
                code=CheckCode.TOTAL,
                passed=total_ok,
                severity=Severity.INFO if total_ok else Severity.ERROR,
                doc_hash=doc.doc_hash,
                expected=str(calc_total),
                actual=str(inv.total),
                message=f"Total verified in {doc.filename}" if total_ok else f"Total mismatch in {doc.filename}",
            )
        )

        # 9. MATCHES_SOURCE check: compare with source ISDOC
        if source_isdoc:
            diffs: list[str] = []
            if inv.invoice_number != source_isdoc.invoice_number:
                diffs.append(f"invoice_number {inv.invoice_number} != {source_isdoc.invoice_number}")
            if inv.ico != source_isdoc.ico:
                diffs.append(f"ico {inv.ico} != {source_isdoc.ico}")
            if inv.total != source_isdoc.total:
                diffs.append(f"total {inv.total} != {source_isdoc.total}")
            if inv.vat_amount != source_isdoc.vat_amount:
                diffs.append(f"vat_amount {inv.vat_amount} != {source_isdoc.vat_amount}")
            if inv.total_without_vat != source_isdoc.total_without_vat:
                diffs.append(f"total_without_vat {inv.total_without_vat} != {source_isdoc.total_without_vat}")

            # Check lines
            if len(inv.lines) != len(source_isdoc.lines):
                diffs.append(f"lines count {len(inv.lines)} != {len(source_isdoc.lines)}")
            else:
                for idx, (il, sl) in enumerate(zip(inv.lines, source_isdoc.lines)):
                    if il.vat_rate != sl.vat_rate:
                        diffs.append(f"line {idx} vat_rate {il.vat_rate} != {sl.vat_rate}")
                    if il.qty != sl.qty:
                        diffs.append(f"line {idx} qty {il.qty} != {sl.qty}")
                    if il.unit_price != sl.unit_price:
                        diffs.append(f"line {idx} unit_price {il.unit_price} != {sl.unit_price}")

            matches = len(diffs) == 0
            checks.append(
                Check(
                    code=CheckCode.MATCHES_SOURCE,
                    passed=matches,
                    severity=Severity.INFO if matches else Severity.ERROR,
                    doc_hash=doc.doc_hash,
                    actual="; ".join(diffs) if diffs else None,
                    message=f"Matches source ISDOC in {doc.filename}" if matches else f"Source mismatch in {doc.filename}: {'; '.join(diffs)}",
                )
            )

        # 10. ICO_ARES check
        if inv.ico:
            ares_res = ares.lookup(inv.ico)
            checks.append(
                Check(
                    code=CheckCode.ICO_ARES,
                    passed=ares_res.exists,
                    severity=Severity.INFO if ares_res.exists else Severity.WARNING,
                    doc_hash=doc.doc_hash,
                    actual=ares_res.name,
                    simulated=ares_res.simulated,
                    message=(
                        f"IČO {inv.ico} verified in ARES ({ares_res.name or 'found'})"
                        if ares_res.exists
                        else f"IČO {inv.ico} not found in ARES"
                    ),
                )
            )

        # 11. DIC_FORMAT check
        if inv.dic:
            dic_ok = bool(DIC_PATTERN.match(inv.dic))
            checks.append(
                Check(
                    code=CheckCode.DIC_FORMAT,
                    passed=dic_ok,
                    severity=Severity.INFO if dic_ok else Severity.WARNING,
                    doc_hash=doc.doc_hash,
                    actual=inv.dic,
                    message=f"DIČ {inv.dic} valid" if dic_ok else f"DIČ {inv.dic} invalid format",
                )
            )

    return VerificationReport(
        seller_id=seller_id,
        package_sha256=job_input.package_sha256,
        blockchain_identifier=blockchain_identifier,
        checks=checks,
    )
