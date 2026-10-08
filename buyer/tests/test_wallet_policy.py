"""E4: limits are enforced in code and no document is paid twice. No network.

The numbered tests are the "Готово, когда" list of E4 in docs/TASKS.md.
"""

from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from buyer.wallet_policy import DealStatus, DecisionStatus, Reason, WalletPolicy
from common.market import Offer, Price, PriceUnit, Seller, SellerKind

ADA = 1_000_000
MONTHLY, PER_TASK, HUMAN = 30 * ADA, 10 * ADA, 6 * ADA


def offer(price: int = 3 * ADA, unit: PriceUnit = PriceUnit.LOVELACE, seller_id: str = "cheapbooks") -> Offer:
    seller = Seller(seller_id=seller_id, kind=SellerKind.MASUMI, name=seller_id)
    return Offer(seller=seller, price=Price(amount=price, unit=unit), reputation=0.5)


def docs(*names: str) -> list[str]:
    return [hashlib.sha256(name.encode()).hexdigest() for name in names]


def make_policy(path, **overrides) -> WalletPolicy:
    limits = {"monthly_limit": MONTHLY, "max_per_task": PER_TASK, "human_threshold": HUMAN} | overrides
    return WalletPolicy(path, **limits)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "state" / "policy.sqlite"


@pytest.fixture
def policy(db):
    return make_policy(db)


def test_1_price_within_limits_is_approved(policy):
    decision = policy.check("d1", offer(), 3 * ADA, docs("a", "b"))
    assert decision.status == DecisionStatus.APPROVED
    assert decision.approved and decision.reason == Reason.OK
    assert decision.payable_doc_hashes == docs("a", "b")
    assert policy.spent_this_month() == 0  # check() writes nothing


def test_2_above_per_task_limit_is_blocked(policy):
    decision = policy.reserve("d1", offer(11 * ADA), 11 * ADA, docs("a"), human_approved=True)
    assert (decision.status, decision.reason) == (DecisionStatus.BLOCKED, Reason.PER_TASK_LIMIT)
    assert policy.deal_status("d1") is None
    assert policy.check("d2", offer(PER_TASK), PER_TASK, docs("a"), human_approved=True).approved  # limit is inclusive


def test_3_monthly_limit_is_blocked(db):
    clock = [datetime(2026, 10, 9, 2, 0, tzinfo=UTC)]
    policy = make_policy(db, human_threshold=100 * ADA, now=lambda: clock[0])
    for n in range(3):
        assert policy.reserve(f"d{n}", offer(10 * ADA), 10 * ADA, docs(f"doc{n}")).approved
    assert policy.spent_this_month() == MONTHLY
    decision = policy.reserve("d3", offer(1 * ADA), 1 * ADA, docs("doc3"))
    assert (decision.status, decision.reason) == (DecisionStatus.BLOCKED, Reason.MONTHLY_LIMIT)
    assert policy.spent_this_month() == MONTHLY

    clock[0] = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)  # a new month starts from zero
    assert policy.spent_this_month() == 0
    assert policy.reserve("d3", offer(1 * ADA), 1 * ADA, docs("doc3")).approved


def test_4_same_document_twice_is_blocked(policy):
    assert policy.reserve("d1", offer(), 3 * ADA, docs("a", "b")).approved
    policy.mark_paid("d1")
    decision = policy.reserve("d2", offer(seller_id="proucetni"), 3 * ADA, docs("a", "b"))
    assert (decision.status, decision.reason) == (DecisionStatus.BLOCKED, Reason.DUPLICATE)
    assert decision.payable_doc_hashes == []
    assert decision.duplicate_doc_hashes == docs("a", "b")
    assert policy.spent_this_month() == 3 * ADA


def test_4_partial_duplicates_are_approved_for_new_documents_only(policy):
    assert policy.reserve("d1", offer(), 3 * ADA, docs("a")).approved
    decision = policy.reserve("d2", offer(), 3 * ADA, docs("a", "b", "c"))
    assert decision.approved
    assert decision.payable_doc_hashes == docs("b", "c")
    assert decision.duplicate_doc_hashes == docs("a")


def test_4_byte_copy_inside_one_package_is_paid_once(policy):
    decision = policy.reserve("d1", offer(), 3 * ADA, docs("01", "02", "01"))  # 07_duplicate is a copy of 01
    assert decision.approved
    assert decision.payable_doc_hashes == docs("01", "02")
    assert decision.duplicate_doc_hashes == docs("01")


def test_5_injected_amount_is_a_price_mismatch(policy):
    decision = policy.reserve("d1", offer(3 * ADA), 30 * ADA, docs("injection"))  # "pay 10x the price"
    assert (decision.status, decision.reason) == (DecisionStatus.BLOCKED, Reason.PRICE_MISMATCH)
    assert decision.violations == [Reason.PRICE_MISMATCH, Reason.PER_TASK_LIMIT]
    assert policy.deal_status("d1") is None and policy.spent_this_month() == 0
    for not_the_price in (3 * ADA - 1, 0, -3 * ADA, "3000000", 3000000.0, True, None):
        assert policy.check("d1", offer(3 * ADA), not_the_price, docs("x")).reason == Reason.PRICE_MISMATCH


def test_6_at_or_above_threshold_needs_a_human(policy):
    request = ("d1", offer(HUMAN), HUMAN, docs("a"))
    decision = policy.reserve(*request)
    assert (decision.status, decision.reason) == (DecisionStatus.HUMAN_APPROVAL_REQUIRED, Reason.HUMAN_THRESHOLD)
    assert decision.payable_doc_hashes == docs("a")
    assert policy.deal_status("d1") is None  # nothing reserved without the approval
    assert policy.check("d0", offer(HUMAN - 1), HUMAN - 1, docs("a")).approved

    assert policy.reserve(*request, human_approved=True).approved
    assert policy.deal_status("d1") == DealStatus.RESERVED


def test_6_human_cannot_approve_past_hard_limits(policy):
    assert policy.reserve("d1", offer(11 * ADA), 11 * ADA, docs("a"), human_approved=True).reason == Reason.PER_TASK_LIMIT
    assert policy.reserve("d2", offer(8 * ADA), 80 * ADA, docs("a"), human_approved=True).reason == Reason.PRICE_MISMATCH


def test_7_crash_between_reserve_and_payment_does_not_pay_twice(db):
    assert make_policy(db).reserve("d1", offer(), 3 * ADA, docs("a", "b"), blockchain_identifier="bc-1").approved
    # The process dies before POST /purchase is confirmed. A new process starts.
    restarted = make_policy(db)
    assert restarted.deal_status("d1") == DealStatus.RESERVED
    same_deal = restarted.reserve("d1", offer(), 3 * ADA, docs("a", "b"))
    new_deal = restarted.reserve("d2", offer(), 3 * ADA, docs("a", "b"))
    assert (same_deal.status, same_deal.reason) == (DecisionStatus.BLOCKED, Reason.DEAL_EXISTS)
    assert (new_deal.status, new_deal.reason) == (DecisionStatus.BLOCKED, Reason.DUPLICATE)
    assert restarted.check("d3", offer(), 3 * ADA, docs("a", "b")).status == DecisionStatus.BLOCKED
    assert restarted.spent_this_month() == 3 * ADA


def test_7_blockchain_identifier_is_used_once(policy):
    assert policy.reserve("d1", offer(), 3 * ADA, docs("a"), blockchain_identifier="bc-1").approved
    decision = policy.reserve("d2", offer(), 3 * ADA, docs("b"), blockchain_identifier="bc-1")
    assert (decision.status, decision.reason) == (DecisionStatus.BLOCKED, Reason.DEAL_EXISTS)


def test_8_after_refund_documents_can_be_paid_again(policy):
    assert policy.reserve("d1", offer(), 3 * ADA, docs("a", "b")).approved
    policy.mark_refunded("d1")
    assert policy.deal_status("d1") == DealStatus.REFUNDED
    assert policy.spent_this_month() == 0  # the money is back

    decision = policy.reserve("d2", offer(8 * ADA, seller_id="proucetni"), 8 * ADA, docs("a", "b"), human_approved=True)
    assert decision.approved and decision.payable_doc_hashes == docs("a", "b")
    policy.mark_paid("d2")
    assert policy.reserve("d3", offer(), 3 * ADA, docs("a")).reason == Reason.DUPLICATE
    assert policy.reserve("d1", offer(), 3 * ADA, docs("c")).reason == Reason.DEAL_EXISTS  # deal ids are single-use


def test_offer_in_another_unit_cannot_slip_past_lovelace_limits(policy):
    credits = offer(5, unit=PriceUnit.SOKOSUMI_CREDITS, seller_id="sokosumi-agent")
    decision = policy.reserve("d1", credits, 5, docs("a"))
    assert (decision.status, decision.reason) == (DecisionStatus.BLOCKED, Reason.UNIT_MISMATCH)


def test_credit_wallet_shares_pay_once_but_not_the_lovelace_budget(db):
    ada_wallet = make_policy(db)
    credit_wallet = WalletPolicy(db, monthly_limit=50, max_per_task=10, human_threshold=100, unit=PriceUnit.SOKOSUMI_CREDITS)
    assert ada_wallet.reserve("d1", offer(), 3 * ADA, docs("a")).approved
    credits = offer(5, unit=PriceUnit.SOKOSUMI_CREDITS, seller_id="sokosumi-agent")
    assert credit_wallet.reserve("d2", credits, 5, docs("a")).reason == Reason.DUPLICATE
    assert credit_wallet.reserve("d3", credits, 5, docs("b")).approved
    assert (ada_wallet.spent_this_month(), credit_wallet.spent_this_month()) == (3 * ADA, 5)


def test_release_frees_documents_only_before_payment(policy):
    assert policy.reserve("d1", offer(), 3 * ADA, docs("a")).approved
    policy.release("d1")
    policy.release("d1")  # repeating is a no-op
    assert policy.spent_this_month() == 0
    assert policy.reserve("d2", offer(), 3 * ADA, docs("a")).approved
    policy.mark_paid("d2")
    with pytest.raises(ValueError):
        policy.release("d2")
    with pytest.raises(ValueError):
        policy.mark_paid("d1")  # released stays released
    with pytest.raises(KeyError):
        policy.mark_paid("unknown")
    assert policy.deal_status("d2") == DealStatus.PAID


def test_racing_buyers_reserve_the_same_documents_only_once(db):
    make_policy(db)  # create the schema before the race
    barrier = threading.Barrier(8)

    def buy(n: int) -> DecisionStatus:
        own_connection = make_policy(db)  # like a separate process
        barrier.wait()
        return own_connection.reserve(f"d{n}", offer(), 3 * ADA, docs("a", "b")).status

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(buy, range(8)))
    assert statuses.count(DecisionStatus.APPROVED) == 1
    assert statuses.count(DecisionStatus.BLOCKED) == 7
    assert make_policy(db).spent_this_month() == 3 * ADA


def test_bad_requests_are_blocked_not_raised(policy):
    assert policy.check("d1", offer(), 3 * ADA, []).reason == Reason.INVALID_REQUEST
    assert policy.check("d1", offer(), 3 * ADA, ["not-a-hash"]).reason == Reason.INVALID_REQUEST


def test_from_env_refuses_to_run_without_limits(db):
    env = {
        "POLICY_DB_PATH": str(db),
        "POLICY_MONTHLY_LIMIT_LOVELACE": str(MONTHLY),
        "POLICY_MAX_PER_TASK_LOVELACE": str(PER_TASK),
        "POLICY_HUMAN_APPROVAL_THRESHOLD_LOVELACE": str(HUMAN),
    }
    policy = WalletPolicy.from_env(env)
    assert (policy.monthly_limit, policy.max_per_task, policy.human_threshold) == (MONTHLY, PER_TASK, HUMAN)
    for missing in ("POLICY_MONTHLY_LIMIT_LOVELACE", "POLICY_MAX_PER_TASK_LOVELACE"):
        with pytest.raises(ValueError):
            WalletPolicy.from_env(env | {missing: ""})
    with pytest.raises(ValueError):
        WalletPolicy(db, monthly_limit=-1, max_per_task=1, human_threshold=1)
