"""Seller side of the Masumi escrow (task E3). Money code.

The firm creates the payment request itself, with short timings, instead of
using pip-masumi, whose fixed +24h submitResultTime makes a refund impossible
within one night (OPEN_QUESTIONS Q2). All calls go to our Payment Service node:

    POST /payment                               create_payment()
    POST /payment/resolve-blockchain-identifier wait_funds_locked()
    POST /payment/submit-result                 submit_result()
    POST /payment/authorize-refund              authorize_refund()

Settings come from the environment: PAYMENT_SERVICE_URL, PAYMENT_API_KEY, NETWORK.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import BaseModel, ConfigDict

from common.hashing import masumi_input_hash, masumi_output_hash
from common.mip003 import StartJobResponse

# Minutes after /start_job, ARCHITECTURE section 5. They satisfy the node's rules:
# payBy <= submitResult - 5, submitResult >= now + 15, unlock >= submitResult + 15,
# externalDispute >= unlock + 15.
PAY_BY_MIN, SUBMIT_RESULT_MIN, UNLOCK_MIN, EXTERNAL_DISPUTE_MIN = 10, 20, 40, 60
FUNDS_LOCKED = "FundsLocked"
# States that mean the buyer's money is in the contract and work may start.
PAID_STATES = frozenset({FUNDS_LOCKED, "ResultSubmitted", "Disputed", "RefundRequested"})


class MasumiPaymentError(Exception):
    """The payment service refused a call or could not be reached."""


class PaymentTimes(BaseModel):
    model_config = ConfigDict(frozen=True)

    pay_by: datetime
    submit_result: datetime
    unlock: datetime
    external_dispute_unlock: datetime


def payment_times(now: datetime) -> PaymentTimes:
    """The four deadlines of one escrow, counted from the moment the job is accepted."""
    return PaymentTimes(
        pay_by=now + timedelta(minutes=PAY_BY_MIN),
        submit_result=now + timedelta(minutes=SUBMIT_RESULT_MIN),
        unlock=now + timedelta(minutes=UNLOCK_MIN),
        external_dispute_unlock=now + timedelta(minutes=EXTERNAL_DISPUTE_MIN),
    )


def create_payment(agent_identifier: str, input_data: Mapping[str, str], purchaser_id: str) -> StartJobResponse:
    """Ask the node for a payment request bound to the hash of exactly this input."""
    times = payment_times(datetime.now(UTC))
    input_hash = masumi_input_hash(input_data, purchaser_id)
    body: dict[str, object] = {
        "network": _network(),
        "agentIdentifier": agent_identifier,
        "inputHash": input_hash,
        "identifierFromPurchaser": purchaser_id,
        "payByTime": _iso(times.pay_by),
        "submitResultTime": _iso(times.submit_result),
        "unlockTime": _iso(times.unlock),
        "externalDisputeUnlockTime": _iso(times.external_dispute_unlock),
    }
    source_index = os.environ.get("SUPPORTED_PAYMENT_SOURCE_INDEX", "0")
    if source_index != "":
        body["supportedPaymentSourceIndex"] = int(source_index)  # required for Web3CardanoV2 sources
    data = _post("/payment", body)
    wallet = data.get("SmartContractWallet")
    source = data.get("PaymentSource")
    raw: dict[str, object] = {
        "job_id": "pending",  # seller/app.py puts its own job id in
        "blockchainIdentifier": data.get("blockchainIdentifier"),
        "agentIdentifier": agent_identifier,
        "sellerVKey": wallet.get("walletVkey") if isinstance(wallet, dict) else None,
        "identifierFromPurchaser": purchaser_id,
        "input_hash": input_hash,
        "payByTime": data.get("payByTime"),
        "submitResultTime": data.get("submitResultTime"),
        "unlockTime": data.get("unlockTime"),
        "externalDisputeUnlockTime": data.get("externalDisputeUnlockTime"),
        # Extras the buyer has to copy into POST /purchase unchanged.
        "smartContractAddress": source.get("smartContractAddress") if isinstance(source, dict) else None,
        "paymentForceLayer": data.get("forceLayer"),
    }
    if "supportedPaymentSourceIndex" in body:
        raw["supportedPaymentSourceIndex"] = body["supportedPaymentSourceIndex"]
    return StartJobResponse.model_validate(raw)


def validate_config() -> None:
    """Validate that required environment variables are set for PAYMENT_MODE=masumi (Contract C1)."""
    url = os.environ.get("PAYMENT_SERVICE_URL", "").strip()
    key = os.environ.get("PAYMENT_API_KEY", "").strip()
    agent_id = os.environ.get("AGENT_IDENTIFIER", "").strip()
    missing: list[str] = []
    if not url:
        missing.append("PAYMENT_SERVICE_URL")
    if not key:
        missing.append("PAYMENT_API_KEY")
    if not agent_id:
        missing.append("AGENT_IDENTIFIER")
    if missing:
        raise MasumiPaymentError(
            f"Missing required Masumi configuration for PAYMENT_MODE=masumi: {', '.join(missing)}"
        )


def payment_state(blockchain_id: str) -> str | None:
    """On-chain state of the escrow as our node sees it, None while nothing is on chain."""
    data = _post("/payment/resolve-blockchain-identifier", {"network": _network(), "blockchainIdentifier": blockchain_id})
    state = data.get("onChainState")
    return state if isinstance(state, str) else None


def wait_funds_locked(blockchain_id: str, timeout: float = 900.0, poll_interval: float = 5.0) -> None:
    """Block until the buyer's funds are locked. Work must not start before that.
    
    Retries across transient network errors until the timeout deadline.
    """
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while True:
        try:
            state = payment_state(blockchain_id)
            if state in PAID_STATES:
                return
        except MasumiPaymentError as exc:
            last_err = exc
        if time.monotonic() >= deadline:
            detail = f", last error: {last_err}" if last_err else ""
            raise MasumiPaymentError(f"funds not locked after {timeout:.0f}s{detail}")
        time.sleep(poll_interval)


def submit_result(
    blockchain_id: str,
    purchaser_id: str,
    input_data: Mapping[str, str],
    result_str: str,
    max_retries: int = 10,
    retry_interval: float = 3.0,
) -> None:
    """Put the hash of the delivered result on chain (MIP-004 output hash, 64 hex).

    Retries on transient errors until submitResultTime or max_retries.
    """
    del input_data  # the input is already bound by inputHash; kept for the E3 signature
    output_hash = masumi_output_hash(result_str, purchaser_id)
    body = {
        "network": _network(),
        "blockchainIdentifier": blockchain_id,
        "submitResultHash": output_hash,
    }
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            _post("/payment/submit-result", body)
            return
        except MasumiPaymentError as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
    raise MasumiPaymentError(f"failed to submit result after {max_retries} attempts: {last_exc}") from last_exc


def authorize_refund(blockchain_id: str, max_retries: int = 5, retry_interval: float = 2.0) -> None:
    """Agree to give the money back. Called from /dispute after the errors were re-checked."""
    body = {"network": _network(), "blockchainIdentifier": blockchain_id}
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            _post("/payment/authorize-refund", body)
            return
        except MasumiPaymentError as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
    raise MasumiPaymentError(f"failed to authorize refund after {max_retries} attempts: {last_exc}") from last_exc


def _network() -> str:
    return os.environ.get("NETWORK", "Preprod")


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _post(path: str, body: Mapping[str, object]) -> dict[str, object]:
    url, key = os.environ.get("PAYMENT_SERVICE_URL", ""), os.environ.get("PAYMENT_API_KEY", "")
    if not url or not key:
        raise MasumiPaymentError("PAYMENT_SERVICE_URL and PAYMENT_API_KEY must be set for PAYMENT_MODE=masumi")
    try:
        response = httpx.post(url.rstrip("/") + path, json=dict(body), headers={"token": key}, timeout=60.0)
    except httpx.HTTPError as exc:
        raise MasumiPaymentError(f"payment service unreachable on {path}: {exc}") from exc
    if response.status_code >= 400:
        raise MasumiPaymentError(f"payment service answered {response.status_code} on {path}: {response.text[:300]}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise MasumiPaymentError(f"payment service sent no JSON on {path}") from exc
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise MasumiPaymentError(f"unexpected answer shape on {path}")
    return data
