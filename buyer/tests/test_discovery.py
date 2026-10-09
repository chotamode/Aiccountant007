import tempfile
from pathlib import Path

import pytest

from buyer.discovery import NoSellerError, discover, select
from buyer.reputation import Outcome, Reputation
from buyer.seller_adapter import SellerAdapterError, SellerAvailability
from common.market import Offer, Price, PriceUnit, Seller, SellerKind


def _make_offer(name: str, price: int, rep: float = 0.5, unit: PriceUnit = PriceUnit.LOVELACE) -> Offer:
    return Offer(
        seller=Seller(seller_id=name, kind=SellerKind.MASUMI, name=name, api_base_url=f"http://test/{name}"),
        price=Price(amount=price, unit=unit),
        reputation=rep,
    )


def test_select_cheapest_within_limits():
    cheap = _make_offer("CheapBooks", 2_000_000, 0.5)
    honest = _make_offer("ProUcetni", 5_000_000, 0.5)
    expensive = _make_offer("Expensive", 15_000_000, 0.8)

    selected = select([expensive, cheap, honest], policy_max=10_000_000, min_reputation=0.4)
    assert selected.seller.seller_id == "CheapBooks"


def test_select_tie_broken_by_reputation():
    o1 = _make_offer("Firm1", 3_000_000, 0.5)
    o2 = _make_offer("Firm2", 3_000_000, 0.8)

    selected = select([o1, o2], policy_max=10_000_000, min_reputation=0.4)
    assert selected.seller.seller_id == "Firm2"


def test_select_drops_other_units_and_low_reputation():
    soko = _make_offer("Soko", 5, 0.9, unit=PriceUnit.SOKOSUMI_CREDITS)
    bad_rep = _make_offer("BadRep", 1_000_000, 0.2)
    honest = _make_offer("ProUcetni", 5_000_000, 0.5)

    selected = select([soko, bad_rep, honest], policy_max=10_000_000, min_reputation=0.4)
    assert selected.seller.seller_id == "ProUcetni"


def test_select_no_seller_raises():
    too_exp = _make_offer("Expensive", 20_000_000, 0.9)
    bad_rep = _make_offer("BadRep", 1_000_000, 0.2)

    with pytest.raises(NoSellerError):
        select([too_exp, bad_rep], policy_max=10_000_000, min_reputation=0.4)


def test_demo_selection_progression():
    db = Path(tempfile.mkdtemp()) / "rep.sqlite"
    rep = Reputation(db)

    # Initially both have default score (1/(0+2) = 0.5)
    cheap = _make_offer("CheapBooks", 2_000_000, rep.score("CheapBooks"))
    honest = _make_offer("ProUcetni", 5_000_000, rep.score("ProUcetni"))

    # Step 1: CheapBooks wins
    first = select([cheap, honest], policy_max=10_000_000, min_reputation=0.4)
    assert first.seller.seller_id == "CheapBooks"

    # CheapBooks fails and gets refunded
    rep.record("CheapBooks", Outcome.REFUNDED, "deal-1")
    # Score is now (0 + 1) / (1 + 2) = 0.333 < 0.4
    cheap_after = _make_offer("CheapBooks", 2_000_000, rep.score("CheapBooks"))
    honest_after = _make_offer("ProUcetni", 5_000_000, rep.score("ProUcetni"))

    # Step 2: CheapBooks is filtered out due to low reputation, ProUcetni wins
    second = select([cheap_after, honest_after], policy_max=10_000_000, min_reputation=0.4)
    assert second.seller.seller_id == "ProUcetni"


def test_discover_with_mock_adapter():
    db = Path(tempfile.mkdtemp()) / "rep.sqlite"
    rep = Reputation(db)

    class MockAdapter:
        def __init__(self, base_url: str):
            self.base_url = base_url

        def availability(self):
            if "offline" in self.base_url:
                raise SellerAdapterError("offline")
            return SellerAvailability(
                name="FirmA",
                price_lovelace=3_000_000,
                pricing_type="fixed",
                unit="lovelace",
                payment_mode="off",
            )

    offers = discover(
        ["http://good", "http://offline"],
        reputation=rep,
        adapter_factory=MockAdapter,
    )
    assert len(offers) == 1
    assert offers[0].seller.name == "FirmA"
    assert offers[0].price.amount == 3_000_000
