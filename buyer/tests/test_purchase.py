"""Tests for buyer/purchase.py and Contracts C3 & C4."""

from __future__ import annotations

import httpx
import pytest

from buyer.purchase import MasumiEscrow, PurchaseError
from common.market import Price, PriceUnit
from common.mip003 import StartJobResponse


def test_contract_c3_refuse_simulated_in_real_escrow():
    escrow = MasumiEscrow(base_url="http://node:3001", api_key="k1")
    start = StartJobResponse(
        job_id="test",
        blockchain_identifier="SIMULATED-12345",
        agent_identifier="agent1",
        seller_vkey="vkey1",
        identifier_from_purchaser="purchaser12345678",
        input_hash="hash",
        pay_by_time="100",
        submit_result_time="200",
        unlock_time="300",
        external_dispute_unlock_time="400",
    )
    with pytest.raises(PurchaseError, match="refusing to pay simulated identifier"):
        escrow.lock(start, {"doc": "data"}, [Price(amount=1000, unit=PriceUnit.LOVELACE)])


def test_contract_c3_wait_state_retries_transient_error(monkeypatch):
    call_count = 0

    def mock_post(url, json=None, headers=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ReadTimeout("Timeout")
        return httpx.Response(200, json={"data": {"onChainState": "FundsLocked", "CurrentTransaction": {"txHash": "abc"}}})

    client = httpx.Client()
    monkeypatch.setattr(client, "post", mock_post)
    escrow = MasumiEscrow(base_url="http://node:3001", api_key="k1", client=client, poll_interval=0.01)

    state = escrow.wait_state("bc-id", {"FundsLocked"}, timeout=5.0)
    assert state.on_chain_state == "FundsLocked"
    assert state.tx_hash == "abc"
    assert call_count >= 2


def test_contract_c4_buyer_real_mode_property(tmp_path):
    from buyer.events_bus import EventBus
    from buyer.orchestrator import Buyer
    from buyer.reputation import Reputation
    from buyer.verifier import AresClient
    from buyer.wallet_policy import WalletPolicy

    bus = EventBus(tmp_path / "events.jsonl")
    policy = WalletPolicy.from_env({
        "POLICY_DB_PATH": str(tmp_path / "policy.sqlite"),
        "POLICY_MONTHLY_LIMIT_LOVELACE": "30000000",
        "POLICY_MAX_PER_TASK_LOVELACE": "10000000",
        "POLICY_HUMAN_APPROVAL_THRESHOLD_LOVELACE": "15000000",
    })
    reputation = Reputation(tmp_path / "rep.sqlite")

    class DummyAres(AresClient):
        def check_ico(self, ico: str) -> bool:
            return True

    # Simulated mode (real_escrow is None)
    b_sim = Buyer(
        bus=bus,
        policy=policy,
        reputation=reputation,
        ares=DummyAres(),
        seller_urls=[],
        real_escrow=None,
    )
    assert b_sim.real_mode is False

    # Real mode (real_escrow is MasumiEscrow)
    real_escrow = MasumiEscrow(base_url="http://node:3001", api_key="k1")
    b_real = Buyer(
        bus=bus,
        policy=policy,
        reputation=reputation,
        ares=DummyAres(),
        seller_urls=[],
        real_escrow=real_escrow,
    )
    assert b_real.real_mode is True
