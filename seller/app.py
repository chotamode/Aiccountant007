"""Accounting-firm agent: MIP-003 endpoints plus /ledger.

    FIRM_PROFILE=honest PORT=8001 PAYMENT_MODE=off python -m seller.app
    FIRM_PROFILE=sloppy PORT=8002 PAYMENT_MODE=off python -m seller.app

PAYMENT_MODE=off runs the job right away and answers /start_job with fake
times and blockchainIdentifier="SIMULATED-...". PAYMENT_MODE=masumi goes
through seller/masumi_payment.py (task E3).
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError

from common.documents import Document
from common.hashing import masumi_input_hash
from common.ledger import Ledger, LedgerEntry, LedgerKind
from common.mip003 import (
    INPUT_SCHEMA,
    JobInput,
    JobResult,
    JobStatus,
    StartJobResponse,
    StatusResponse,
    new_purchaser_id,
)
from seller.processing import process
from seller.profiles import FirmProfile, load_profile

LOVELACE_PER_ADA = Decimal(1_000_000)
MINUTE_MS = 60_000
# Demo timings from ARCHITECTURE section 5, minutes after /start_job.
PAY_BY_MIN, SUBMIT_RESULT_MIN, UNLOCK_MIN, EXTERNAL_DISPUTE_MIN = 10, 20, 40, 60
EXAMPLE_FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "a_mini.isdoc"


class PaymentMode(StrEnum):
    OFF = "off"
    MASUMI = "masumi"


class StartJobRequest(BaseModel):
    """MIP-003 body. input_data is accepted as a dict or as [{key, value}]."""

    identifier_from_purchaser: str = Field(
        default_factory=new_purchaser_id, pattern=r"^[0-9a-fA-F]{14,26}$"
    )
    input_data: dict[str, str] | list[dict[str, Any]]

    def input_dict(self) -> dict[str, str]:
        if isinstance(self.input_data, dict):
            return self.input_data
        return {str(item["key"]): str(item["value"]) for item in self.input_data}


class _Job(BaseModel):
    job_id: str
    status: JobStatus
    purchaser_id: str
    input_data: dict[str, str]
    blockchain_identifier: str
    result: str | None = None
    error: str | None = None


def _simulated_start(job: _Job, profile: FirmProfile, now_ms: int) -> StartJobResponse:
    return StartJobResponse(
        job_id=job.job_id,
        blockchain_identifier=job.blockchain_identifier,
        agent_identifier=os.environ.get("AGENT_IDENTIFIER") or f"SIMULATED-{profile.key}",
        seller_vkey=os.environ.get("SELLER_VKEY") or "SIMULATED",
        identifier_from_purchaser=job.purchaser_id,
        input_hash=masumi_input_hash(job.input_data, job.purchaser_id),
        pay_by_time=str(now_ms + PAY_BY_MIN * MINUTE_MS),
        submit_result_time=str(now_ms + SUBMIT_RESULT_MIN * MINUTE_MS),
        unlock_time=str(now_ms + UNLOCK_MIN * MINUTE_MS),
        external_dispute_unlock_time=str(now_ms + EXTERNAL_DISPUTE_MIN * MINUTE_MS),
    )


def create_app(profile: FirmProfile | None = None, payment_mode: str | None = None) -> FastAPI:
    profile = profile or load_profile()
    mode = PaymentMode(payment_mode or os.environ.get("PAYMENT_MODE", PaymentMode.OFF))
    simulated = mode == PaymentMode.OFF

    app = FastAPI(title=f"{profile.name} (MIP-003)")
    jobs: dict[str, _Job] = {}
    ledger = Ledger(seller_name=profile.name)
    lock = threading.Lock()

    def run_job(job: _Job, job_input: JobInput) -> None:
        """Do the work and book revenue + costs. Called once the job is paid."""
        try:
            result, costs = process(job_input, profile, job_id=job.job_id)
        except Exception as exc:  # noqa: BLE001  # one bad job must not take the agent down
            with lock:
                job.status, job.error = JobStatus.FAILED, str(exc)
            return
        revenue = LedgerEntry(
            job_id=job.job_id,
            kind=LedgerKind.REVENUE,
            amount=Decimal(profile.price_lovelace) / LOVELACE_PER_ADA,
            unit="ADA",
            description=f"escrow for {len(job_input.documents)} documents",
            simulated=simulated,
        )
        with lock:
            ledger.entries.extend([revenue, *(c.model_copy(update={"simulated": simulated}) for c in costs)])
            job.result, job.status = result.to_result_string(), JobStatus.COMPLETED

    def run_paid_job(job: _Job, job_input: JobInput) -> None:
        # TODO(E3): interface from TASKS.md E3; module lands with feat/e3-seller-payment.
        from seller import masumi_payment

        try:
            masumi_payment.wait_funds_locked(job.blockchain_identifier)
        except Exception as exc:  # noqa: BLE001
            with lock:
                job.status, job.error = JobStatus.FAILED, f"payment not locked: {exc}"
            return
        with lock:
            job.status = JobStatus.RUNNING
        run_job(job, job_input)
        if job.status == JobStatus.COMPLETED and job.result is not None:
            masumi_payment.submit_result(
                job.blockchain_identifier, job.purchaser_id, job.input_data, job.result
            )

    @app.get("/availability")
    def availability() -> dict[str, Any]:
        return {
            "status": "available",
            "type": "masumi-agent",
            "agentName": profile.name,
            "profile": profile.key,
            "price_lovelace": profile.price_lovelace,
            "payment_mode": mode.value,
            "message": "SIMULATED payments" if simulated else "Masumi escrow on preprod",
        }

    @app.get("/input_schema")
    def input_schema() -> dict[str, Any]:
        return INPUT_SCHEMA

    @app.post("/start_job")
    def start_job(body: StartJobRequest) -> dict[str, Any]:
        input_data = body.input_dict()
        try:
            job_input = JobInput.from_input_data(input_data)
        except (KeyError, ValueError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail=f"invalid input_data: {exc}") from exc

        job_id = uuid.uuid4().hex
        if simulated:
            job = _Job(
                job_id=job_id,
                status=JobStatus.RUNNING,
                purchaser_id=body.identifier_from_purchaser,
                input_data=input_data,
                blockchain_identifier=f"SIMULATED-{job_id}",
            )
            with lock:
                jobs[job_id] = job
            response = _simulated_start(job, profile, int(time.time() * 1000))
            run_job(job, job_input)
        else:
            try:
                from seller import masumi_payment
            except ImportError as exc:
                raise HTTPException(status_code=501, detail="PAYMENT_MODE=masumi needs E3") from exc
            response = masumi_payment.create_payment(
                os.environ["AGENT_IDENTIFIER"], input_data, body.identifier_from_purchaser
            )
            job = _Job(
                job_id=job_id,
                status=JobStatus.AWAITING_PAYMENT,
                purchaser_id=body.identifier_from_purchaser,
                input_data=input_data,
                blockchain_identifier=response.blockchain_identifier,
            )
            response = response.model_copy(update={"job_id": job_id})
            with lock:
                jobs[job_id] = job
            threading.Thread(target=run_paid_job, args=(job, job_input), daemon=True).start()

        payload = response.model_dump(by_alias=False)
        # Buyer copies these into Masumi POST /purchase, so expose camelCase too.
        payload.update(
            {
                "id": response.job_id,
                "blockchainIdentifier": response.blockchain_identifier,
                "agentIdentifier": response.agent_identifier,
                "sellerVKey": response.seller_vkey,
                "identifierFromPurchaser": response.identifier_from_purchaser,
                "payByTime": response.pay_by_time,
                "submitResultTime": response.submit_result_time,
                "unlockTime": response.unlock_time,
                "externalDisputeUnlockTime": response.external_dispute_unlock_time,
                "status": "success",
                "simulated": simulated,
            }
        )
        return payload

    @app.get("/status")
    def status(job_id: str) -> dict[str, Any]:
        with lock:
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="job not found")
            response = StatusResponse(job_id=job.job_id, status=job.status, result=job.result)
            payload = response.model_dump()
            if job.error:
                payload["error"] = job.error
        return payload

    @app.get("/ledger")
    def get_ledger() -> dict[str, Any]:
        with lock:
            data = ledger.model_dump(mode="json")
            data["totals"] = {
                kind.value: {unit: str(v) for unit, v in ledger.totals(kind).items()} for kind in LedgerKind
            }
        return data

    @app.get("/example_output.json")
    def example_output() -> dict[str, Any]:
        documents = [Document.from_bytes(EXAMPLE_FIXTURE.name, EXAMPLE_FIXTURE.read_bytes())]
        result, _ = process(JobInput.build(documents), profile, job_id="example")
        return {"result": JobResult.model_validate(result).to_result_string()}

    @app.post("/dispute")
    def dispute(body: dict[str, Any]) -> dict[str, Any]:
        job_id = str(body.get("job_id", ""))
        with lock:
            job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

        report = body.get("report", {})
        checks = report.get("checks", []) if isinstance(report, dict) else []
        blocking = [c for c in checks if isinstance(c, dict) and not c.get("passed") and c.get("severity") == "error"]

        # Deterministic re-check: sloppy confirmed its own injected errors
        authorized = profile.sloppy and len(blocking) > 0
        if authorized:
            if not simulated:
                from seller import masumi_payment
                try:
                    masumi_payment.authorize_refund(job.blockchain_identifier)
                except Exception as exc:  # noqa: BLE001
                    return {
                        "job_id": job.job_id,
                        "authorized": False,
                        "message": f"failed to authorize refund on chain: {exc}",
                        "simulated": False,
                    }
            refund_entry = LedgerEntry(
                job_id=job.job_id,
                kind=LedgerKind.COST,
                amount=Decimal(profile.price_lovelace) / LOVELACE_PER_ADA,
                unit="ADA",
                description=f"refund for dispute on job {job.job_id}",
                simulated=simulated,
            )
            with lock:
                ledger.entries.append(refund_entry)
            return {
                "job_id": job.job_id,
                "authorized": True,
                "message": f"{profile.name} confirmed the errors and authorized the refund",
                "simulated": simulated,
            }

        return {
            "job_id": job.job_id,
            "authorized": False,
            "message": f"{profile.name} re-checked output and refused the refund",
            "simulated": simulated,
        }

    return app


def main() -> None:
    import uvicorn

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8001")))


if __name__ == "__main__":
    main()
