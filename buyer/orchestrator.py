"""The client's agent, end to end: find a firm, hand the documents over, lock the
price in escrow, verify the work, pay for good work and take the money back for bad.

    python -m buyer.orchestrator --scenario demo

Every step is published to the event feed (buyer/state/events.jsonl, shown by the
dashboard). The orchestrator never decides about money by itself: every payment
goes through buyer.wallet_policy first, and nobody presses a button below the
human-approval threshold.
"""

from __future__ import annotations

import argparse
import os
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from buyer.discovery import NoSellerError, discover, select
from buyer.events_bus import EventBus
from buyer.purchase import (
    Escrow,
    EscrowState,
    MasumiEscrow,
    OnChainState,
    PurchaseError,
    SimulatedEscrow,
    is_simulated,
)
from buyer.reputation import Outcome, Reputation
from buyer.seller_adapter import Mip003Adapter, SellerAdapterError
from buyer.vault import build_job_input, load_documents, manifest
from buyer.verifier import AresClient, HttpAresClient, verify
from buyer.wallet_policy import Decision, DecisionStatus, Reason, WalletPolicy
from common.checks import CheckCode, Severity, VerificationReport
from common.documents import Document
from common.events import Actor, Event, EventType
from common.market import Offer, Price
from common.mip003 import JobResult, JobStatus, StartJobResponse, new_purchaser_id

DEFAULT_STATE_DIR = Path("buyer/state")
DEFAULT_INVOICES = Path("data/invoices")
INJECTION_FACTOR = 10  # the demo document asks to "pay 10x the price"


class DealStatus(StrEnum):
    PAID = "paid"  # work verified, documents settled
    REFUND_PENDING = "refund_pending"  # work rejected, refund requested from escrow
    REFUNDED = "refunded"  # the money is back
    BLOCKED = "blocked"  # wallet policy said no, nothing was paid
    FAILED = "failed"  # no seller, no result or escrow trouble


class DealResult(BaseModel):
    deal_id: str
    title: str
    status: DealStatus
    seller_id: str | None = None
    blockchain_identifier: str | None = None
    job_id: str | None = None
    seller_url: str | None = None
    simulated: bool = False
    detail: str = ""


@dataclass(slots=True)
class Buyer:
    """Everything one buyer agent needs; all parts are injected so tests run without network."""

    bus: EventBus
    policy: WalletPolicy
    reputation: Reputation
    ares: AresClient
    seller_urls: Sequence[str]
    adapter_factory: Callable[[str], Mip003Adapter] = Mip003Adapter
    real_escrow: Escrow | None = None  # None: only sellers with PAYMENT_MODE=off can be paid
    min_reputation: float | None = None
    pace: float = 0.0  # seconds between events, so a screen recording can be followed
    poll_interval: float = 2.0
    job_timeout: float = 1500.0
    lock_timeout: float = 900.0
    approval_timeout: float = 600.0
    _simulated_escrow: SimulatedEscrow = field(init=False)

    def __post_init__(self) -> None:
        self._simulated_escrow = SimulatedEscrow()

    # --- event feed ---

    def emit(
        self,
        event_type: EventType,
        msg: str,
        *,
        deal_id: str | None = None,
        actor: Actor = Actor.BUYER,
        simulated: bool = False,
        tx_url: str | None = None,
        data: Mapping[str, object] | None = None,
    ) -> None:
        self.bus.publish(
            Event(
                actor=actor,
                type=event_type,
                msg=msg,
                deal_id=deal_id,
                simulated=simulated,
                tx_url=tx_url,
                data=dict(data or {}),
            )
        )
        if self.pace:
            time.sleep(self.pace)

    # --- one deal ---

    def run_deal(self, title: str, documents: Sequence[Document]) -> DealResult:
        deal_id = uuid.uuid4().hex[:12]  # fresh for every attempt: the policy blocks a known deal_id
        result = DealResult(deal_id=deal_id, title=title, status=DealStatus.FAILED)

        offer = self._choose_seller(deal_id, title)
        if offer is None:
            return result.model_copy(update={"detail": "no seller passed price and reputation filters"})
        result = result.model_copy(update={"seller_id": offer.seller.seller_id, "seller_url": offer.seller.api_base_url})

        entries = manifest(list(documents))
        package = build_job_input(list(documents)).package_sha256
        self.emit(
            EventType.DOCS_HASHED,
            f"{len(entries)} documents hashed (sha256), package {package[:16]}…",
            deal_id=deal_id,
            data={"package_sha256": package, "documents": ", ".join(e.filename for e in entries)},
        )

        price = offer.price.amount
        decision = self.policy.check(deal_id, offer, price, [d.doc_hash for d in documents])
        human_approved = False
        if decision.status == DecisionStatus.HUMAN_APPROVAL_REQUIRED:
            human_approved = self._wait_for_human(deal_id, decision)
            if not human_approved:
                return result.model_copy(update={"status": DealStatus.BLOCKED, "detail": "no human approval in time"})
        elif decision.status == DecisionStatus.BLOCKED:
            self._report_block(deal_id, decision)
            return result.model_copy(update={"status": DealStatus.BLOCKED, "detail": decision.reason.value})

        payable = _first_per_hash(documents, decision.payable_doc_hashes)
        dropped = [d.filename for d in documents if d not in payable]
        if dropped:
            self.emit(
                EventType.DUPLICATE_BLOCKED,
                f"Not paying twice: {', '.join(dropped)} already paid or a byte copy of another document",
                deal_id=deal_id,
                data={"dropped": ", ".join(dropped)},
            )

        job_input = build_job_input(payable)
        input_data = job_input.to_input_data()  # sent and hashed exactly as is
        adapter = self.adapter_factory(offer.seller.api_base_url or "")
        try:
            start = adapter.start(job_input, new_purchaser_id())
        except SellerAdapterError as exc:
            self.emit(EventType.ERROR, f"{offer.seller.name} did not accept the job: {exc}", deal_id=deal_id)
            return result.model_copy(update={"detail": str(exc)})
        escrow = self._escrow_for(start)
        result = result.model_copy(
            update={
                "blockchain_identifier": start.blockchain_identifier,
                "job_id": start.job_id,
                "simulated": escrow.simulated,
            }
        )
        self.emit(
            EventType.JOB_STARTED,
            f"{offer.seller.name} accepted {len(payable)} documents and asks {offer.price} in escrow",
            deal_id=deal_id,
            actor=Actor.SELLER,
            simulated=escrow.simulated,
            data={"job_id": start.job_id, "input_hash": start.input_hash},
        )

        # Reserve and pay. The reservation is written before any money call (pay-once).
        decision = self.policy.reserve(
            deal_id,
            offer,
            price,
            [d.doc_hash for d in payable],
            blockchain_identifier=start.blockchain_identifier,
            human_approved=human_approved,
        )
        if not decision.approved:
            self._report_block(deal_id, decision)
            return result.model_copy(update={"status": DealStatus.BLOCKED, "detail": decision.reason.value})
        self.emit(EventType.POLICY_APPROVED, f"Wallet policy approved: {decision.message}", deal_id=deal_id)

        try:
            escrow.lock(start, input_data, [offer.price])
            locked = escrow.wait_state(
                start.blockchain_identifier,
                {OnChainState.FUNDS_LOCKED, OnChainState.RESULT_SUBMITTED},
                timeout=self.lock_timeout,
            )
        except PurchaseError as exc:
            # Whether funds moved is unknown here, so the reservation stays: no second payment.
            self.emit(EventType.ERROR, f"Escrow failed, documents stay reserved: {exc}", deal_id=deal_id)
            return result.model_copy(update={"detail": str(exc)})
        self.emit(
            EventType.ESCROW_LOCKED,
            f"{offer.price} locked in escrow for {offer.seller.name}",
            deal_id=deal_id,
            simulated=escrow.simulated,
            tx_url=locked.tx_url,
            data={"blockchain_identifier": start.blockchain_identifier[:40]},
        )

        job_result = self._wait_for_result(deal_id, offer, adapter, start)
        if job_result is None:
            self.reputation.record(offer.seller.seller_id, Outcome.FAILED, deal_id)
            return result.model_copy(update={"detail": "seller delivered no result"})
        submitted = self._safe_state(escrow, start.blockchain_identifier)
        self.emit(
            EventType.RESULT_SUBMITTED,
            f"{offer.seller.name} delivered {len(job_result.invoices)} extracted invoices",
            deal_id=deal_id,
            actor=Actor.SELLER,
            simulated=escrow.simulated,
            tx_url=submitted.tx_url if submitted and submitted.on_chain_state == OnChainState.RESULT_SUBMITTED else None,
        )

        report = verify(
            job_input,
            job_result,
            self.ares,
            seller_id=offer.seller.seller_id,
            blockchain_identifier=start.blockchain_identifier,
        )
        self._report_warnings(deal_id, payable, report)
        if report.passed:
            return self._accept(deal_id, offer, result, report)
        return self._reject(deal_id, offer, result, report, adapter, escrow, payable)

    def _choose_seller(self, deal_id: str, title: str) -> Offer | None:
        self.emit(EventType.DISCOVERY_STARTED, f"{title}: looking for accounting firms", deal_id=deal_id)
        offers = discover(self.seller_urls, reputation=self.reputation, adapter_factory=self.adapter_factory)
        for offer in offers:
            self.emit(
                EventType.OFFER_FOUND,
                f"{offer.seller.name}: {offer.price}, reputation {offer.reputation:.2f} ({offer.deals_seen} deals)",
                deal_id=deal_id,
                data={"seller": offer.seller.name, "price": str(offer.price), "reputation": f"{offer.reputation:.2f}"},
            )
        try:
            chosen = select(offers, self.policy.max_per_task, self.min_reputation)
        except NoSellerError as exc:
            self.emit(EventType.ERROR, f"No seller to hire: {exc}", deal_id=deal_id)
            return None
        self.emit(
            EventType.SELLER_SELECTED,
            f"Selected {chosen.seller.name}: cheapest offer with enough reputation ({chosen.price})",
            deal_id=deal_id,
        )
        return chosen

    def _escrow_for(self, start: StartJobResponse) -> Escrow:
        if is_simulated(start):
            return self._simulated_escrow
        if self.real_escrow is None:
            raise PurchaseError("seller wants real escrow but no payment service is configured")
        return self.real_escrow

    def _wait_for_human(self, deal_id: str, decision: Decision) -> bool:
        self.emit(EventType.HUMAN_APPROVAL_REQUIRED, decision.message, deal_id=deal_id)
        deadline = time.monotonic() + self.approval_timeout
        while time.monotonic() < deadline:
            approved = any(
                e.deal_id == deal_id and e.type == EventType.HUMAN_APPROVED for e in self.bus.history()
            )
            if approved:
                return True
            time.sleep(self.poll_interval)
        self.emit(EventType.POLICY_BLOCKED, "No human approval in time, nothing was paid", deal_id=deal_id)
        return False

    def _report_block(self, deal_id: str, decision: Decision) -> None:
        event_type = EventType.DUPLICATE_BLOCKED if decision.reason == Reason.DUPLICATE else EventType.POLICY_BLOCKED
        self.emit(
            event_type,
            f"Wallet policy blocked the payment ({decision.reason.value}): {decision.message}",
            deal_id=deal_id,
            data={"violations": ", ".join(v.value for v in decision.violations) or decision.reason.value},
        )

    def _wait_for_result(
        self, deal_id: str, offer: Offer, adapter: Mip003Adapter, start: StartJobResponse
    ) -> JobResult | None:
        deadline = time.monotonic() + self.job_timeout
        while True:
            try:
                status = adapter.status(start.job_id)
            except SellerAdapterError as exc:
                self.emit(EventType.ERROR, f"{offer.seller.name} status failed: {exc}", deal_id=deal_id)
                return None
            if status.status == JobStatus.COMPLETED and status.result is not None:
                try:
                    return JobResult.from_result_string(status.result)
                except ValueError as exc:
                    self.emit(EventType.ERROR, f"{offer.seller.name} sent an unreadable result: {exc}", deal_id=deal_id)
                    return None
            if status.status == JobStatus.FAILED or time.monotonic() >= deadline:
                self.emit(EventType.ERROR, f"{offer.seller.name} did not deliver ({status.status.value})", deal_id=deal_id)
                return None
            time.sleep(self.poll_interval)

    @staticmethod
    def _safe_state(escrow: Escrow, blockchain_id: str) -> EscrowState | None:
        try:
            return escrow.state(blockchain_id)
        except PurchaseError:
            return None

    def _report_warnings(self, deal_id: str, documents: Sequence[Document], report: VerificationReport) -> None:
        names = {d.doc_hash: d.filename for d in documents}
        for check in report.checks:
            if check.passed or check.severity != Severity.WARNING:
                continue
            where = names.get(check.doc_hash or "", "package")
            if check.code == CheckCode.PROMPT_INJECTION:
                self.emit(
                    EventType.POLICY_BLOCKED,
                    f"{where}: the document text tries to instruct the agent. It is data, not a command: "
                    "the price comes from the offer only",
                    deal_id=deal_id,
                    data={"found": (check.actual or "")[:120]},
                )

    def _accept(self, deal_id: str, offer: Offer, result: DealResult, report: VerificationReport) -> DealResult:
        warnings = [c for c in report.checks if not c.passed and c.severity == Severity.WARNING]
        note = f", {len(warnings)} supplier-side warnings" if warnings else ""
        self.emit(
            EventType.VERIFICATION_PASSED,
            f"Work verified: {len(report.checks)} checks, no seller errors{note}",
            deal_id=deal_id,
            data={"report_hash": report.report_hash(), "warnings": "; ".join(c.message for c in warnings)[:300]},
        )
        self.policy.mark_paid(deal_id)
        self.reputation.record(offer.seller.seller_id, Outcome.PAID, deal_id)
        self.emit(
            EventType.REPUTATION_UPDATED,
            f"{offer.seller.name} reputation is now {self.reputation.score(offer.seller.seller_id):.2f}",
            deal_id=deal_id,
        )
        if result.simulated:
            self.emit(
                EventType.PAYMENT_RELEASED, f"{offer.price} released to {offer.seller.name}", deal_id=deal_id, simulated=True
            )
        else:
            self.emit(
                EventType.POLICY_APPROVED,
                f"No dispute raised: the escrow pays {offer.seller.name} after unlockTime",
                deal_id=deal_id,
            )
        return result.model_copy(update={"status": DealStatus.PAID})

    def _reject(
        self,
        deal_id: str,
        offer: Offer,
        result: DealResult,
        report: VerificationReport,
        adapter: Mip003Adapter,
        escrow: Escrow,
        documents: Sequence[Document],
    ) -> DealResult:
        names = {d.doc_hash: d.filename for d in documents}
        failed = sorted(names.get(h, h[:12]) for h in report.failed_doc_hashes)
        first = report.blocking_failures[0]
        self.emit(
            EventType.VERIFICATION_FAILED,
            f"Work rejected: errors in {', '.join(failed) or 'the package'}. {first.message}",
            deal_id=deal_id,
            data={
                "report_hash": report.report_hash(),
                "failed_checks": ", ".join(sorted({c.code.value for c in report.blocking_failures})),
            },
        )
        self.reputation.record(offer.seller.seller_id, Outcome.REFUNDED, deal_id)
        self.emit(
            EventType.REPUTATION_UPDATED,
            f"{offer.seller.name} reputation dropped to {self.reputation.score(offer.seller.seller_id):.2f}",
            deal_id=deal_id,
        )
        blockchain_id = result.blockchain_identifier or ""
        try:
            requested = escrow.request_refund(blockchain_id)
        except PurchaseError as exc:
            self.emit(EventType.ERROR, f"Refund request failed: {exc}", deal_id=deal_id)
            return result.model_copy(update={"detail": str(exc)})
        self.emit(
            EventType.REFUND_REQUESTED,
            f"Refund of {offer.price} requested from escrow, verification report attached",
            deal_id=deal_id,
            simulated=escrow.simulated,
            tx_url=requested.tx_url,
        )
        try:
            answer = adapter.dispute(result.job_id or "", report)
        except SellerAdapterError as exc:
            self.emit(
                EventType.ERROR,
                f"{offer.seller.name} did not answer the dispute, it now needs Masumi admins (manual): {exc}",
                deal_id=deal_id,
            )
            return result.model_copy(update={"status": DealStatus.REFUND_PENDING, "detail": str(exc)})
        if not answer.authorized:
            self.emit(
                EventType.ERROR,
                f"{offer.seller.name} refused the refund: dispute goes to Masumi admins (manual, not automated)",
                deal_id=deal_id,
                actor=Actor.SELLER,
            )
            return result.model_copy(update={"status": DealStatus.REFUND_PENDING, "detail": answer.message})
        self.emit(
            EventType.REFUND_AUTHORIZED,
            f"{offer.seller.name} re-checked its own output, confirmed the errors and authorized the refund",
            deal_id=deal_id,
            actor=Actor.SELLER,
            simulated=answer.simulated,
        )
        return result.model_copy(update={"status": DealStatus.REFUND_PENDING})

    # --- settling a refund ---

    def settle_refund(self, deal: DealResult, offer_price: Price | None = None, timeout: float = 0.0) -> DealResult:
        """Wait until the refund is back on our side, then free the documents for another seller."""
        if deal.status != DealStatus.REFUND_PENDING or deal.blockchain_identifier is None:
            return deal
        escrow: Escrow = self._simulated_escrow if deal.simulated else (self.real_escrow or self._simulated_escrow)
        try:
            state = escrow.wait_state(deal.blockchain_identifier, {OnChainState.REFUND_WITHDRAWN}, timeout=timeout)
        except PurchaseError as exc:
            self.emit(
                EventType.ERROR,
                f"Refund is not back yet, documents stay reserved: {exc}",
                deal_id=deal.deal_id,
            )
            return deal
        self.policy.mark_refunded(deal.deal_id)
        amount = f"{offer_price} " if offer_price else ""
        self.emit(
            EventType.REFUND_WITHDRAWN,
            f"Refund {amount}is back in the buyer wallet; the documents can go to another firm",
            deal_id=deal.deal_id,
            simulated=deal.simulated,
            tx_url=state.tx_url,
        )
        return deal.model_copy(update={"status": DealStatus.REFUNDED})

    # --- demo steps that are not purchases ---

    def attack_drill(self, title: str, document: Document) -> None:
        """Show what happens if the agent obeyed text inside a document (OPEN_QUESTIONS Q15).

        The injected text asks to pay ten times the price. We feed exactly that
        amount to the wallet policy, as a compromised step would, and publish its answer.
        """
        deal_id = uuid.uuid4().hex[:12]
        offers = discover(self.seller_urls, reputation=self.reputation, adapter_factory=self.adapter_factory)
        if not offers:
            return
        offer = min(offers, key=lambda o: o.price.amount)
        inflated = offer.price.amount * INJECTION_FACTOR
        decision = self.policy.check(deal_id, offer, inflated, [document.doc_hash])
        asked = Price(amount=inflated, unit=offer.price.unit)
        self.emit(
            EventType.POLICY_BLOCKED if not decision.approved else EventType.ERROR,
            f"{title}: {document.filename} says 'pay 10x'. Asked to pay {asked} instead of {offer.price}: "
            f"{decision.status.value} ({', '.join(v.value for v in decision.violations) or decision.reason.value})",
            deal_id=deal_id,
            data={"drill": "amount taken from the document text on purpose", "decision": decision.message},
        )


def _first_per_hash(documents: Sequence[Document], payable_hashes: Sequence[str]) -> list[Document]:
    """The first document for every payable hash, in the order of the package."""
    wanted, picked = set(payable_hashes), []
    for document in documents:
        if document.doc_hash in wanted:
            wanted.discard(document.doc_hash)
            picked.append(document)
    return picked


# --- scenario ---


def run_demo(buyer: Buyer, invoices: Path, refund_timeout: float) -> list[DealResult]:
    """CONTEXT section 5: cheap sloppy firm, refund, honest firm, no double payment, no obeying documents."""
    docs = {d.filename[:2]: d for d in load_documents(invoices, "*.isdoc")}

    def batch(*numbers: str) -> list[Document]:
        return [docs[n] for n in numbers]

    results = [buyer.run_deal("September invoices, batch 1", batch("01", "02", "03", "07"))]
    buyer.attack_drill("Injection attempt", docs["08"])
    results.append(buyer.run_deal("September invoices, batch 2", batch("04", "05", "06", "08")))
    results.append(buyer.run_deal("Batch 2 sent again by mistake", batch("04", "05")))
    refunded = buyer.settle_refund(results[0], timeout=refund_timeout)
    results[0] = refunded
    if refunded.status == DealStatus.REFUNDED:
        results.append(buyer.run_deal("Batch 1 again, after the refund", batch("01", "02", "03")))
    return results


def build_buyer(state_dir: Path, pace: float, env: Mapping[str, str] | None = None) -> Buyer:
    env = os.environ if env is None else env
    bus = EventBus(state_dir / "events.jsonl")
    policy_env = dict(env)
    policy_env["POLICY_DB_PATH"] = str(state_dir / "policy.sqlite")
    real_escrow: Escrow | None = None
    if env.get("PAYMENT_SERVICE_URL") and env.get("PAYMENT_API_KEY"):
        real_escrow = MasumiEscrow.from_env(env=env)
    urls = [u.strip() for u in env.get("SELLER_URLS", "").split(",") if u.strip()]
    return Buyer(
        bus=bus,
        policy=WalletPolicy.from_env(policy_env),
        reputation=Reputation(state_dir / "reputation.sqlite"),
        ares=HttpAresClient(cache_path=state_dir / "ares_cache.json"),
        seller_urls=urls,
        real_escrow=real_escrow,
        pace=pace,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=["demo"], default="demo")
    parser.add_argument("--invoices", type=Path, default=DEFAULT_INVOICES)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR, help="policy, reputation and event feed")
    parser.add_argument("--pace", type=float, default=1.0, help="seconds between events")
    parser.add_argument("--refund-timeout", type=float, default=0.0, help="how long to wait for RefundWithdrawn")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    buyer = build_buyer(args.state_dir, args.pace)
    for deal in run_demo(buyer, args.invoices, args.refund_timeout):
        tag = " [SIMULATED]" if deal.simulated else ""
        print(f"{deal.title:<34} {deal.status.value:<15} {deal.seller_id or '-':<12}{tag} {deal.detail}")


if __name__ == "__main__":
    main()
