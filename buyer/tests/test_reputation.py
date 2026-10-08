"""B4: a new seller scores 0.5, a refund drops it below, a deal is counted once."""

from __future__ import annotations

import pytest

from buyer.reputation import Outcome, Reputation

MIN_REPUTATION = 0.4  # default from .env.example


@pytest.fixture
def reputation():
    return Reputation()


def test_new_seller_starts_at_half(reputation):
    assert reputation.score("new") == 0.5
    assert reputation.deals_seen("new") == 0


def test_one_refund_drops_below_half(reputation):
    assert reputation.record("cheapbooks", Outcome.REFUNDED, "deal-1")
    assert reputation.score("cheapbooks") == pytest.approx(1 / 3)
    assert reputation.score("cheapbooks") < 0.5


def test_same_deal_is_not_counted_twice(reputation):
    assert reputation.record("s", "paid", "deal-1")
    assert not reputation.record("s", "paid", "deal-1")
    assert not reputation.record("s", "refunded", "deal-1")  # first outcome stays
    assert reputation.deals_seen("s") == 1
    assert reputation.score("s") == pytest.approx(2 / 3)


def test_demo_story_cheap_seller_falls_below_threshold(reputation):
    reputation.record("cheapbooks", Outcome.REFUNDED, "deal-1")
    reputation.record("proucetni", Outcome.PAID, "deal-2")
    assert reputation.score("cheapbooks") < MIN_REPUTATION < reputation.score("proucetni")


def test_failed_counts_against_the_seller(reputation):
    reputation.record("s", Outcome.PAID, "deal-1")
    reputation.record("s", Outcome.FAILED, "deal-2")
    assert reputation.score("s") == pytest.approx(2 / 4)


def test_sokosumi_rating_is_the_starting_value(reputation):
    prior = 4.5 / 5  # metrics.ratings.average / 5
    assert reputation.score("soko", prior=prior) == pytest.approx(0.9)
    reputation.record("soko", Outcome.FAILED, "deal-1")
    assert reputation.score("soko", prior=prior) == pytest.approx(1.8 / 3)


def test_survives_restart(tmp_path):
    path = tmp_path / "state" / "reputation.sqlite"
    Reputation(path).record("s", Outcome.REFUNDED, "deal-1")
    restarted = Reputation(path)
    assert restarted.deals_seen("s") == 1
    assert not restarted.record("s", Outcome.PAID, "deal-1")


def test_rejects_bad_input(reputation):
    with pytest.raises(ValueError):
        reputation.record("s", "bribed", "deal-1")
    with pytest.raises(ValueError):
        reputation.score("s", prior=1.5)
