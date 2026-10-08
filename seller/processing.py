"""The firm's actual work: documents in, extracted invoices and P&L out.

Pure function, no network, no FastAPI, no Masumi. seller/app.py calls it
once the job is paid (or right away with PAYMENT_MODE=off).
"""

from __future__ import annotations

from decimal import Decimal

from common.documents import DocumentFormat
from common.invoice import ExtractedInvoice, ExtractionStatus
from common.isdoc import parse_isdoc
from common.ledger import LedgerEntry, LedgerKind
from common.mip003 import JobInput, JobResult
from seller.profiles import FirmProfile, apply_profile

# ISDOC is structured XML, reading it costs nothing.
ISDOC_COST_USD = Decimal(0)


def process(
    job: JobInput, profile: FirmProfile, job_id: str | None = None
) -> tuple[JobResult, list[LedgerEntry]]:
    """Extract every document, then let the profile do its (mis)work.

    Returns one ExtractedInvoice per input document, in input order, and the
    job's cost entries. Revenue is booked by the payment flow (E3), not here.
    """
    job_id = job_id or job.package_sha256[:16]
    invoices: list[ExtractedInvoice] = []
    costs: list[LedgerEntry] = []

    for document in job.documents:
        if document.format == DocumentFormat.ISDOC:
            invoices.append(parse_isdoc(document.content, filename=document.filename))
            costs.append(
                LedgerEntry(
                    job_id=job_id,
                    kind=LedgerKind.COST,
                    amount=ISDOC_COST_USD,
                    unit="USD",
                    description=f"ISDOC parse: {document.filename}",
                )
            )
        else:
            # TODO(B7): PDF -> Apify OCR; book the OCR price as a COST entry then.
            invoices.append(
                ExtractedInvoice(
                    doc_hash=document.doc_hash,
                    filename=document.filename,
                    status=ExtractionStatus.UNREADABLE,
                )
            )

    result = JobResult(
        seller_name=profile.name,
        package_sha256=job.package_sha256,
        invoices=apply_profile(invoices, profile),
    )
    return result, costs
