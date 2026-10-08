"""ISDOC (Czech e-invoice XML) -> ExtractedInvoice.

Shared by the seller (extraction) and the buyer's verifier (ground truth),
so both sides read a document the same way. Element lookup ignores XML
namespaces: ISDOC 5.x and 6.x differ only in the namespace URI.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation

from common.hashing import doc_hash
from common.invoice import ExtractedInvoice, ExtractionStatus, InvoiceLine

Element = ET.Element


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(parent: Element | None, *path: str) -> Element | None:
    """Follow a path of local names, first match at each step."""
    node = parent
    for name in path:
        if node is None:
            return None
        node = next((c for c in node if _local(c.tag) == name), None)
    return node


def _children(parent: Element | None, name: str) -> list[Element]:
    return [] if parent is None else [c for c in parent if _local(c.tag) == name]


def _text(parent: Element | None, *path: str) -> str | None:
    node = _child(parent, *path)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _decimal(parent: Element | None, *path: str) -> Decimal | None:
    value = _text(parent, *path)
    if value is None:
        return None
    try:
        return Decimal(value.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None


def _date(parent: Element | None, *path: str) -> date | None:
    value = _text(parent, *path)
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _bank_account(root: Element) -> str | None:
    """Czech "number/bank code" if present, else IBAN."""
    details = _child(root, "PaymentMeans", "Payment", "Details")
    number, bank_code = _text(details, "ID"), _text(details, "BankCode")
    if number and bank_code:
        return f"{number}/{bank_code}"
    iban = _text(details, "IBAN")
    if iban:
        return iban.replace(" ", "")
    # Some exporters only fill the alternate account list.
    alt = _child(root, "PaymentMeans", "AlternateBankAccounts", "AlternateBankAccount")
    number, bank_code = _text(alt, "ID"), _text(alt, "BankCode")
    if number and bank_code:
        return f"{number}/{bank_code}"
    return _text(alt, "IBAN")


def _line(node: Element) -> InvoiceLine:
    qty = _decimal(node, "InvoicedQuantity") or Decimal(1)
    unit_price = _decimal(node, "UnitPrice")
    if unit_price is None:
        # Fall back to the line total when the unit price is missing.
        line_total = _decimal(node, "LineExtensionAmount") or Decimal(0)
        unit_price = line_total / qty if qty else line_total
    return InvoiceLine(
        desc=_text(node, "Item", "Description") or _text(node, "Note") or "",
        qty=qty,
        unit_price=unit_price,
        vat_rate=_decimal(node, "ClassifiedTaxCategory", "Percent") or Decimal(0),
    )


def parse_isdoc(content: bytes, filename: str | None = None) -> ExtractedInvoice:
    """Extract the CONTEXT section 6 fields from an ISDOC file.

    Never raises on bad input: anything that is not a readable ISDOC invoice
    comes back as status=unreadable, so one broken file does not fail a job.
    `doc_hash` equals `Document.doc_hash` for the same bytes.
    """
    unreadable = ExtractedInvoice(
        doc_hash=doc_hash(content), filename=filename, status=ExtractionStatus.UNREADABLE
    )
    # Refuse DTDs outright: ISDOC never needs them and they enable entity bombs.
    if b"<!DOCTYPE" in content[:4096].upper():
        return unreadable
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return unreadable
    if _local(root.tag) != "Invoice":
        return unreadable

    supplier = _child(root, "AccountingSupplierParty", "Party")
    totals = _child(root, "LegalMonetaryTotal")
    lines = [_line(n) for n in _children(_child(root, "InvoiceLines"), "InvoiceLine")]

    total_without_vat = _decimal(totals, "TaxExclusiveAmount")
    total = _decimal(totals, "TaxInclusiveAmount")
    vat_amount = _decimal(root, "TaxTotal", "TaxAmount")
    if vat_amount is None and total is not None and total_without_vat is not None:
        vat_amount = total - total_without_vat

    return ExtractedInvoice(
        doc_hash=doc_hash(content),
        filename=filename,
        status=ExtractionStatus.OK,
        supplier_name=_text(supplier, "PartyName", "Name"),
        ico=_text(supplier, "PartyIdentification", "ID"),
        dic=_text(supplier, "PartyTaxScheme", "CompanyID"),
        invoice_number=_text(root, "ID"),
        issue_date=_date(root, "IssueDate"),
        currency=_text(root, "LocalCurrencyCode") or "CZK",
        lines=lines,
        total_without_vat=total_without_vat,
        vat_amount=vat_amount,
        total=total,
        bank_account=_bank_account(root),
    )
