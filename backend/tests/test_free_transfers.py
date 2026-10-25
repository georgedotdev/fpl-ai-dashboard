"""Free transfers aren't public, so we replay the season. Each case is small enough to check by hand.

Notation in comments: "FT n" = free transfers available going into that gameweek's deadline.
"""

from app.manager.free_transfers import derive_free_transfers
from app.rules import load_rules
from tests import factories as f

RULES = load_rules("2026_27")


def derive(rows, chips=None, started=1):
    return derive_free_transfers(
        [f.history([r]).current[0] for r in rows], f.chip_plays(chips or {}), started, RULES
    )


def test_nothing_before_the_first_deadline_means_unlimited():
    result = derive([], started=9)
    assert result.value is None


def test_after_the_first_gameweek_you_have_one():
    # GW1 squad picked freely -> FT 1 for GW2
    assert derive([f.gw_row(1)]).value == 1


def test_unused_transfers_roll_over():
    # GW2 FT1 used 0 -> GW3 FT2; used 0 -> GW4 FT3
    assert derive([f.gw_row(1), f.gw_row(2), f.gw_row(3)]).value == 3


def test_banked_transfers_cap_at_five():
    rows = [f.gw_row(gw) for gw in range(1, 10)]  # eight roll-overs after GW1
    assert derive(rows).value == 5


def test_using_some_leaves_the_rest_plus_one():
    # GW2 FT1 used 0 -> FT2; GW3 used 1 -> 1 left + 1 = FT2 for GW4
    assert derive([f.gw_row(1), f.gw_row(2), f.gw_row(3, transfers=1)]).value == 2


def test_taking_a_hit_resets_to_one():
    # GW2 FT1, made 2 transfers (one -4 hit) -> 0 left + 1 = FT1 for GW3
    result = derive([f.gw_row(1), f.gw_row(2, transfers=2, cost=4)])
    assert result.value == 1
    assert result.corrections == []


def test_wildcard_week_keeps_banked_transfers():
    # FT1 at GW2, rolled -> FT2 at GW3; GW3 wildcard with 9 transfers uses none -> FT3 for GW4
    rows = [f.gw_row(1), f.gw_row(2), f.gw_row(3, transfers=9)]
    result = derive(rows, chips={3: "wildcard"})
    assert result.value == 3
    assert "Wildcard/Free Hit" in result.note


def test_free_hit_week_keeps_banked_transfers():
    rows = [f.gw_row(1), f.gw_row(2, transfers=11)]
    assert derive(rows, chips={2: "freehit"}).value == 2


def test_triple_captain_week_counts_transfers_normally():
    rows = [f.gw_row(1), f.gw_row(2, transfers=1)]
    assert derive(rows, chips={2: "3xc"}).value == 1


def test_late_joiner_starts_counting_from_their_first_gameweek():
    # Joined in GW5: GW5 squad free -> FT1 for GW6; rolled -> FT2 for GW7
    assert derive([f.gw_row(5), f.gw_row(6)], started=5).value == 2


def test_resyncs_when_fpl_charged_a_hit_we_did_not_expect():
    # We think FT3 at GW4, but FPL charged -4 for 3 transfers: they really had 2.
    rows = [f.gw_row(1), f.gw_row(2), f.gw_row(3), f.gw_row(4, transfers=3, cost=4)]
    result = derive(rows)
    assert result.value == 1
    assert result.corrections == ["GW4: FPL charged 1 hit(s) where we expected 0; re-synced"]


def test_resyncs_when_fpl_charged_nothing_but_we_expected_a_hit():
    # We think FT1 at GW2, FPL charged nothing for 2 transfers: they had at least 2.
    rows = [f.gw_row(1), f.gw_row(2, transfers=2, cost=0), f.gw_row(3)]
    result = derive(rows)
    assert result.value == 2  # 0 left after GW2, +1, then rolled once more
    assert result.corrections == ["GW2: FPL charged 0 hit(s) where we expected 1; re-synced"]
