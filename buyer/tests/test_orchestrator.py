import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from buyer.events_bus import EventBus
from buyer.orchestrator import Buyer, DealStatus, run_demo
from buyer.reputation import Reputation
from buyer.seller_adapter import Mip003Adapter
from buyer.verifier import AresResult
from buyer.wallet_policy import WalletPolicy
from seller.app import create_app
from seller.profiles import HONEST, SLOPPY

DATA_DIR = Path("data/invoices")


class MockAres:
    def lookup(self, ico: str) -> AresResult:
        return AresResult(ico=ico, name="Mock Supplier s.r.o.", exists=True, simulated=True)


def test_orchestrator_demo_scenario():
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = Path(tmp)
        bus = EventBus(state_dir / "events.jsonl")
        policy = WalletPolicy(state_dir / "policy.sqlite", monthly_limit=30_000_000, max_per_task=10_000_000, human_threshold=6_000_000)
        reputation = Reputation(state_dir / "reputation.sqlite")
        ares = MockAres()

        sloppy_client = TestClient(create_app(SLOPPY, payment_mode="off"))
        honest_client = TestClient(create_app(HONEST, payment_mode="off"))

        def adapter_factory(url: str) -> Mip003Adapter:
            if "8002" in url or "sloppy" in url:
                return Mip003Adapter(url, client=sloppy_client)
            return Mip003Adapter(url, client=honest_client)

        seller_urls = ["http://seller:8002", "http://seller:8001"]

        buyer = Buyer(
            bus=bus,
            policy=policy,
            reputation=reputation,
            ares=ares,
            seller_urls=seller_urls,
            adapter_factory=adapter_factory,
            pace=0.0,
        )

        results = run_demo(buyer, DATA_DIR, refund_timeout=1.0)
        assert len(results) == 4

        # 1. Batch 1 initially sent to CheapBooks -> rejected by verifier -> refund settled -> REFUNDED
        assert results[0].status == DealStatus.REFUNDED
        assert results[0].seller_id == "CheapBooks"

        # 2. Batch 2 sent to ProÚčetní -> verified -> PAID
        assert results[1].status == DealStatus.PAID
        assert results[1].seller_id == "ProÚčetní"

        # 3. Batch 2 sent again -> BLOCKED by policy as duplicate
        assert results[2].status == DealStatus.BLOCKED

        # 4. Batch 1 sent again after refund -> goes to ProÚčetní -> PAID
        assert results[3].status == DealStatus.PAID
        assert results[3].seller_id == "ProÚčetní"

        # Verify event stream
        history = bus.history()
        assert len(history) > 10
        # Check that events contain key demo checkpoints
        event_types = {e.type for e in history}
        assert "verification_failed" in event_types
        assert "refund_requested" in event_types
        assert "refund_authorized" in event_types
        assert "verification_passed" in event_types
        assert "duplicate_blocked" in event_types
