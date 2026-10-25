"""Selling price = purchase price + half of any rise, rounded down to £0.1m (tenths here)."""

import pytest

from app.manager.selling_prices import latest_purchases, price_at_gameweek, selling_price
from app.rules import load_rules
from tests import factories as f

FEE = load_rules("2026_27").transfers.sell_on_fee


@pytest.mark.parametrize(
    ("purchase", "now", "expected"),
    [
        (50, 50, 50),  # no change
        (50, 52, 51),  # +0.2 -> keep 0.1
        (50, 53, 51),  # +0.3 -> 0.15 rounds down to 0.1
        (50, 51, 50),  # +0.1 -> 0.05 rounds down to nothing
        (50, 48, 48),  # falls are passed on in full
        (100, 107, 103),
    ],
)
def test_selling_price(purchase, now, expected):
    assert selling_price(purchase, now, FEE) == expected


def test_latest_purchase_wins_when_a_player_was_bought_twice():
    transfers = [
        f.transfer(element_in=7, cost_in=60, element_out=3, event=2),
        f.transfer(element_in=3, cost_in=55, element_out=7, event=4),
        f.transfer(element_in=7, cost_in=64, element_out=9, event=6),
    ]
    bought = latest_purchases(transfers, ignore_gameweeks=set())
    assert bought[7].element_in_cost == 64
    assert bought[3].element_in_cost == 55


def test_free_hit_transfers_are_ignored_because_the_squad_reverts():
    transfers = [
        f.transfer(element_in=7, cost_in=60, element_out=3, event=2),
        f.transfer(element_in=7, cost_in=70, element_out=12, event=5),  # during a Free Hit
    ]
    bought = latest_purchases(transfers, ignore_gameweeks={5})
    assert bought[7].element_in_cost == 60


def test_price_at_gameweek_uses_that_rounds_fixture():
    summary = f.element_summary({1: 50, 2: 50, 3: 51, 4: 52})
    assert price_at_gameweek(summary, 3) == 51


def test_price_at_gameweek_falls_back_to_the_next_fixture_in_a_blank():
    summary = f.element_summary({1: 50, 3: 51})
    assert price_at_gameweek(summary, 2) == 51


def test_price_at_gameweek_unknown_without_history():
    assert price_at_gameweek(f.element_summary({}), 2) is None
