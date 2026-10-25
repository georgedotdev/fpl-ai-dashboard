"""Estimate what each squad player would sell for.

Exact selling prices are login-only. FPL's rule: you get your purchase price plus a share
(sell_on_fee, 50%) of any rise, rounded down to £0.1m; falls are passed on in full.
Purchase prices come from the public transfer log; for players held since the manager's
first gameweek, from the player's price history.
"""

from fractions import Fraction
from math import floor

from app.fpl.models import ElementSummary, Transfer


def selling_price(purchase: int, now: int, sell_on_fee: float) -> int:
    if now <= purchase:
        return now
    return purchase + floor(Fraction(str(sell_on_fee)) * (now - purchase))


def latest_purchases(transfers: list[Transfer], ignore_gameweeks: set[int]) -> dict[int, Transfer]:
    """Most recent transfer-in per player, skipping gameweeks whose squad reverted (Free Hit)."""
    latest: dict[int, Transfer] = {}
    for t in sorted(transfers, key=lambda t: t.time):
        if t.event not in ignore_gameweeks:
            latest[t.element_in] = t
    return latest


def price_at_gameweek(summary: ElementSummary, gameweek: int) -> int | None:
    """A player's price in a given gameweek, from their fixture history.

    In a blank gameweek there's no fixture row, so use the player's next fixture.
    """
    rows = sorted(summary.history, key=lambda r: r.round)
    for row in rows:
        if row.round >= gameweek:
            return row.value
    return None
