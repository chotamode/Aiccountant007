"""Seller discovery and selection: who sells accounting work, at what price, and whom to pick.

Tonight offers come from the /availability of our own sellers (SELLER_URLS). Discovery through
the Masumi registry is added later by the integrator: it only has to produce Offers as well, so
offer_from_availability, discover and select stay separate pieces.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence

from buyer.reputation import Reputation
from buyer.seller_adapter import Mip003Adapter, SellerAdapterError, SellerAvailability
from common.market import Offer, Price, PriceUnit, Seller, SellerKind

DEFAULT_MIN_REPUTATION = 0.4  # fallback for MIN_REPUTATION, same as .env.example


class NoSellerError(Exception):
    """Nobody passes the filters."""


def offer_from_availability(base_url: str, availability: SellerAvailability, reputation: Reputation) -> Offer:
    """One of our own sellers as an Offer: its /availability price, our reputation score for it."""
    seller_id = availability.name
    return Offer(
        seller=Seller(seller_id=seller_id, kind=SellerKind.MASUMI, name=availability.name, api_base_url=base_url),
        price=Price(amount=availability.price_lovelace, unit=PriceUnit.LOVELACE),
        reputation=reputation.score(seller_id),
        deals_seen=reputation.deals_seen(seller_id),
    )


def discover(
    seller_urls: Sequence[str] | None = None,
    *,
    reputation: Reputation,
    adapter_factory: Callable[[str], Mip003Adapter] = Mip003Adapter,
) -> list[Offer]:
    """Ask every seller URL for its /availability; seller_urls=None reads SELLER_URLS.

    A seller that does not answer is skipped. The order of the URLs is kept.
    """
    urls = _seller_urls_from_env() if seller_urls is None else seller_urls
    offers: list[Offer] = []
    for url in urls:
        try:
            availability = adapter_factory(url).availability()
        except SellerAdapterError:
            continue
        offers.append(offer_from_availability(url, availability, reputation))
    return offers


def select(offers: Sequence[Offer], policy_max: int, min_reputation: float | None = None) -> Offer:
    """The cheapest offer that is trusted enough and within policy_max (lovelace).

    Dropped: offers priced in another unit (Sokosumi credits must never be compared with
    lovelace), offers with reputation below min_reputation (default: MIN_REPUTATION, else 0.4)
    and offers priced above policy_max. On equal prices the higher reputation wins.
    """
    threshold = _min_reputation_from_env() if min_reputation is None else min_reputation
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"min_reputation must be within 0..1, got {threshold}")

    kept: list[Offer] = []
    other_unit = distrusted = too_expensive = 0
    for offer in offers:
        if offer.price.unit != PriceUnit.LOVELACE:
            other_unit += 1
        elif offer.reputation < threshold:
            distrusted += 1
        elif offer.price.amount > policy_max:
            too_expensive += 1
        else:
            kept.append(offer)
    if kept:
        return min(kept, key=lambda offer: (offer.price.amount, -offer.reputation))

    reasons = [
        f"{count} {why}"
        for count, why in (
            (other_unit, "not priced in lovelace"),
            (distrusted, f"with reputation below {threshold:g}"),
            (too_expensive, f"priced above {policy_max} lovelace"),
        )
        if count
    ]
    detail = f"dropped {len(offers)} of {len(offers)} offers: {', '.join(reasons)}" if reasons else "no offers"
    raise NoSellerError(f"no seller passes the filters ({detail})")


def _seller_urls_from_env() -> list[str]:
    urls = os.environ.get("SELLER_URLS", "").split(",")
    return [url.strip() for url in urls if url.strip()]


def _min_reputation_from_env() -> float:
    raw = os.environ.get("MIN_REPUTATION", "").strip()
    return float(raw) if raw else DEFAULT_MIN_REPUTATION
