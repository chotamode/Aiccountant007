"""Escrow on the buyer side: lock the price, watch the on-chain state, ask for a refund.

Money code (task E5). Two rails behind one interface:

- MasumiEscrow talks to our Masumi Payment Service node (Cardano preprod). Real funds.
- SimulatedEscrow is for sellers running PAYMENT_MODE=off. It moves nothing and
  says so: every state it reports has simulated=True.

Both refuse to pay when the seller's input_hash does not match the documents we
sent (ARCHITECTURE section 3): the escrow would otherwise be bound to other data.
Spending limits are not checked here; buyer.wallet_policy runs before lock().

    python -m buyer.purchase --smoke     # live check against the node from .env
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Collection, Mapping, Sequence
from enum import StrEnum
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict

from common.events import Actor, Event, EventType
from common.hashing import masumi_input_hash
from common.market import Price, PriceUnit
from common.mip003 import StartJobResponse

SIMULATED_PREFIX = "SIMULATED-"
EXPLORER_TX_URL = "https://preprod.cardanoscan.io/transaction/{tx_hash}"

Publish = Callable[[Event], object]


class PurchaseError(Exception):
    """The escrow could not be created, read or refunded. Nothing is retried silently."""


class InputHashMismatchError(PurchaseError):
    """The seller bound the payment to an input other than the one we sent. We do not pay."""


class OnChainState(StrEnum):
    """Escrow states of the Masumi contract that the buyer reacts to."""

    FUNDS_LOCKED = "FundsLocked"
    RESULT_SUBMITTED = "ResultSubmitted"
    REFUND_REQUESTED = "RefundRequested"
    DISPUTED = "Disputed"
    WITHDRAWN = "Withdrawn"
    REFUND_WITHDRAWN = "RefundWithdrawn"
    DISPUTED_WITHDRAWN = "DisputedWithdrawn"
    FUNDS_OR_DATUM_INVALID = "FundsOrDatumInvalid"


class EscrowState(BaseModel):
    model_config = ConfigDict(frozen=True)

    blockchain_identifier: str
    on_chain_state: str | None  # an OnChainState value, None while nothing is on chain yet
    tx_hash: str | None = None
    simulated: bool = False

    @property
    def tx_url(self) -> str | None:
        return EXPLORER_TX_URL.format(tx_hash=self.tx_hash) if self.tx_hash else None


class Escrow(Protocol):
    simulated: bool

    def lock(self, start: StartJobResponse, input_data: Mapping[str, str], amounts: Sequence[Price]) -> str: ...

    def state(self, blockchain_id: str) -> EscrowState: ...

    def wait_state(self, blockchain_id: str, states: Collection[str], timeout: float = 600.0) -> EscrowState: ...

    def request_refund(self, blockchain_id: str) -> EscrowState: ...


def check_input_hash(start: StartJobResponse, input_data: Mapping[str, str]) -> None:
    """Raise unless the seller's input_hash is the MIP-004 hash of what we actually sent."""
    expected = masumi_input_hash(input_data, start.identifier_from_purchaser)
    if start.input_hash != expected:
        raise InputHashMismatchError(
            f"seller input_hash {start.input_hash[:16]}… differs from ours {expected[:16]}…, not paying"
        )


def is_simulated(start: StartJobResponse) -> bool:
    return start.blockchain_identifier.startswith(SIMULATED_PREFIX)


class SimulatedEscrow:
    """Stand-in for sellers with PAYMENT_MODE=off. No chain, no money, everything flagged."""

    simulated = True

    def __init__(self, publish: Publish | None = None) -> None:
        self._publish = publish
        self._states: dict[str, str] = {}

    def lock(self, start: StartJobResponse, input_data: Mapping[str, str], amounts: Sequence[Price]) -> str:
        check_input_hash(start, input_data)
        self._states[start.blockchain_identifier] = OnChainState.FUNDS_LOCKED
        self._emit(EventType.ESCROW_LOCKED, f"{_total(amounts)} locked in escrow", start.blockchain_identifier)
        return start.blockchain_identifier

    def state(self, blockchain_id: str) -> EscrowState:
        return EscrowState(
            blockchain_identifier=blockchain_id, on_chain_state=self._states.get(blockchain_id), simulated=True
        )

    def wait_state(self, blockchain_id: str, states: Collection[str], timeout: float = 600.0) -> EscrowState:
        # Simulated time is instant: the escrow moves to the first state the caller waits for.
        if blockchain_id not in self._states:
            raise PurchaseError(f"unknown simulated purchase {blockchain_id}")
        self._states[blockchain_id] = next(iter(states))
        return self.state(blockchain_id)

    def request_refund(self, blockchain_id: str) -> EscrowState:
        if blockchain_id not in self._states:
            raise PurchaseError(f"unknown simulated purchase {blockchain_id}")
        self._states[blockchain_id] = OnChainState.DISPUTED
        self._emit(EventType.REFUND_REQUESTED, "Refund requested from escrow", blockchain_id)
        return self.state(blockchain_id)

    def _emit(self, event_type: EventType, msg: str, blockchain_id: str) -> None:
        if self._publish is not None:
            self._publish(
                Event(
                    actor=Actor.BUYER,
                    type=event_type,
                    msg=msg,
                    simulated=True,
                    data={"blockchain_identifier": blockchain_id},
                )
            )


class MasumiEscrow:
    """Our Masumi Payment Service node: POST /purchase, resolve, request-refund."""

    simulated = False

    def __init__(
        self,
        base_url: str,
        api_key: str,
        network: str = "Preprod",
        client: httpx.Client | None = None,
        publish: Publish | None = None,
        poll_interval: float = 10.0,
    ) -> None:
        self._client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=60.0)
        self._headers = {"token": api_key}
        self._network = network
        self._publish = publish
        self._poll_interval = poll_interval

    @classmethod
    def from_env(cls, publish: Publish | None = None, env: Mapping[str, str] | None = None) -> MasumiEscrow:
        env = os.environ if env is None else env
        url, key = env.get("PAYMENT_SERVICE_URL", ""), env.get("PAYMENT_API_KEY", "")
        if not url or not key:
            raise PurchaseError("PAYMENT_SERVICE_URL and PAYMENT_API_KEY must be set for real escrow")
        return cls(url, key, network=env.get("NETWORK", "Preprod"), publish=publish)

    def lock(self, start: StartJobResponse, input_data: Mapping[str, str], amounts: Sequence[Price]) -> str:
        if is_simulated(start):
            raise PurchaseError(
                f"refusing to pay simulated identifier {start.blockchain_identifier} in real escrow mode"
            )
        check_input_hash(start, input_data)  # before any money call
        body: dict[str, object] = {
            "blockchainIdentifier": start.blockchain_identifier,
            "network": self._network,
            "inputHash": start.input_hash,
            "sellerVkey": start.seller_vkey,
            "agentIdentifier": start.agent_identifier,
            "identifierFromPurchaser": start.identifier_from_purchaser,
            "payByTime": start.pay_by_time,
            "submitResultTime": start.submit_result_time,
            "unlockTime": start.unlock_time,
            "externalDisputeUnlockTime": start.external_dispute_unlock_time,
            "Amounts": [_amount(price) for price in amounts],
        }
        # V2 payment sources: the seller's choice is signed into the identifier, pass it through unchanged.
        extra = start.model_extra or {}
        for field in ("supportedPaymentSourceIndex", "paymentForceLayer", "smartContractAddress"):
            if extra.get(field) is not None:
                body[field] = extra[field]
        self._post("/purchase", body)
        self._emit(
            EventType.JOB_STARTED,
            f"Purchase of {_total(amounts)} submitted to the Masumi node, waiting for the lock transaction",
            start.blockchain_identifier,
        )
        return start.blockchain_identifier

    def state(self, blockchain_id: str) -> EscrowState:
        data = self._post(
            "/purchase/resolve-blockchain-identifier",
            {"blockchainIdentifier": blockchain_id, "network": self._network},
        )
        transaction = data.get("CurrentTransaction")
        tx_hash = transaction.get("txHash") if isinstance(transaction, dict) else None
        state = data.get("onChainState")
        return EscrowState(
            blockchain_identifier=blockchain_id,
            on_chain_state=state if isinstance(state, str) else None,
            tx_hash=tx_hash if isinstance(tx_hash, str) else None,
        )

    def wait_state(self, blockchain_id: str, states: Collection[str], timeout: float = 600.0) -> EscrowState:
        deadline = time.monotonic() + timeout
        last_err: Exception | None = None
        while True:
            try:
                current = self.state(blockchain_id)
                if current.on_chain_state in states:
                    return current
                if current.on_chain_state == OnChainState.FUNDS_OR_DATUM_INVALID:
                    raise PurchaseError(f"escrow for {blockchain_id[:24]}… is invalid on chain")
            except PurchaseError as exc:
                last_err = exc
            if time.monotonic() >= deadline:
                wanted = ", ".join(sorted(states))
                detail = f", last error: {last_err}" if last_err else ""
                raise PurchaseError(
                    f"escrow did not reach {wanted} within {timeout:.0f}s{detail}"
                )
            time.sleep(self._poll_interval)

    def request_refund(self, blockchain_id: str) -> EscrowState:
        self._post("/purchase/request-refund", {"blockchainIdentifier": blockchain_id, "network": self._network})
        self._emit(EventType.REFUND_REQUESTED, "Refund requested from the Masumi escrow", blockchain_id)
        return self.state(blockchain_id)

    def _post(self, path: str, body: Mapping[str, object]) -> dict[str, object]:
        try:
            response = self._client.post(path, json=dict(body), headers=self._headers)
        except httpx.HTTPError as exc:
            raise PurchaseError(f"payment service unreachable on {path}: {exc}") from exc
        if response.status_code >= 400:
            raise PurchaseError(f"payment service answered {response.status_code} on {path}: {response.text[:300]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise PurchaseError(f"payment service sent no JSON on {path}") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise PurchaseError(f"unexpected answer shape on {path}")
        return data

    def _emit(self, event_type: EventType, msg: str, blockchain_id: str) -> None:
        if self._publish is not None:
            self._publish(
                Event(actor=Actor.BUYER, type=event_type, msg=msg, data={"blockchain_identifier": blockchain_id})
            )


def _amount(price: Price) -> dict[str, str]:
    if price.unit != PriceUnit.LOVELACE:
        raise PurchaseError(f"escrow in {price.unit.value} is not supported, only lovelace")
    return {"unit": "", "amount": str(price.amount)}  # Masumi: unit "" is ADA in lovelace


def _total(amounts: Sequence[Price]) -> str:
    return " + ".join(str(price) for price in amounts) or "nothing"


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Masumi buyer purchase smoke test")
    parser.add_argument("--smoke", action="store_true", help="Check node connectivity and health")
    parser.add_argument("--confirm", action="store_true", help="Confirm real transaction execution")
    args = parser.parse_args()

    url = os.environ.get("PAYMENT_SERVICE_URL", "")
    key = os.environ.get("PAYMENT_API_KEY", "")
    network = os.environ.get("NETWORK", "Preprod")

    if not url or not key:
        print(f"[!] Real escrow not configured: PAYMENT_SERVICE_URL={'set' if url else 'unset'}, PAYMENT_API_KEY={'set' if key else 'unset'}")
        print("    Running in SIMULATED escrow mode.")
        sys.exit(0)

    print(f"[*] Node URL: {url}")
    print(f"[*] Network: {network}")

    try:
        resp = httpx.get(url.rstrip("/") + "/health", timeout=5.0)
        print(f"[*] Health check: HTTP {resp.status_code} -> {resp.text}")
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Node unreachable: {exc}")
        sys.exit(1)

    if not args.confirm:
        print("[+] Smoke check passed (dry-run mode). Use --confirm to perform live escrow operations.")
    else:
        print("[*] Live confirmed mode active.")


if __name__ == "__main__":
    main()
