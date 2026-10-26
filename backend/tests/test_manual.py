import pytest

from app.game import GameData
from app.manager.manual import InvalidSquad, ManualSquad, build_manual_state
from app.rules import load_rules
from tests import factories as f

RULES = load_rules("2026_27")


def game(extra=()) -> GameData:
    """Players 1-15 are a valid squad (2 GKP, 5 DEF, 5 MID, 3 FWD over teams 1-6); GW8 current."""
    return GameData(f.bootstrap(elements=f.standard_squad_elements() + list(extra), current=8), [])


def squad(ids=range(1, 16), **kw) -> ManualSquad:
    return ManualSquad(**({"player_ids": list(ids), "bank": 15, "free_transfers": 2} | kw))


def test_valid_squad_builds_a_labelled_state():
    state = build_manual_state(squad(chips_available=["bboost-1", "3xc-1"]), game(), RULES)
    assert state.planning_gameweek == 9 and state.team_id == 0
    assert len(state.squad) == 15
    assert state.bank.value == 15 and state.bank.source == "user_override"
    assert state.free_transfers.value == 2 and state.free_transfers.source == "user_override"
    assert state.team_value.value == 15 + 15 * 50
    assert all(p.selling_price.source == "derived" and p.purchase_price.value is None for p in state.squad)
    assert state.past_gameweeks == []


def test_placeholder_xi_is_a_legal_formation_with_goalkeeper_first_on_the_bench():
    state = build_manual_state(squad(), game(), RULES)
    starters = [p.position for p in state.squad if p.bench_order is None]
    assert len(starters) == 11 and starters.count("GKP") == 1
    assert starters.count("DEF") >= 3 and starters.count("MID") >= 2 and starters.count("FWD") >= 1
    bench = sorted((p for p in state.squad if p.bench_order), key=lambda p: p.bench_order)
    assert bench[0].position == "GKP"


def test_chips_ticked_are_available_the_rest_used_and_unopened_ones_upcoming():
    state = build_manual_state(squad(chips_available=["wildcard-1"]), game(), RULES)
    chips = {(c.chip, c.half): c.state for c in state.chips}
    assert chips[("wildcard", 1)] == "available"
    assert chips[("freehit", 1)] == "used"
    assert chips[("wildcard", 2)] == "upcoming"


@pytest.mark.parametrize(
    ("ids", "message"),
    [
        (range(1, 15), "Pick exactly 15 players (you have 14)."),
        ([1, 1, *range(3, 16)], "Each player can only be picked once."),
        ([*range(1, 15), 999], "Unknown player id(s): 999."),
    ],
)
def test_wrong_size_duplicates_and_unknown_players_are_rejected(ids, message):
    with pytest.raises(InvalidSquad) as exc:
        build_manual_state(squad(ids), game(), RULES)
    assert message in exc.value.problems


def test_wrong_shape_is_rejected():
    # Swap forward 15 for an extra midfielder 16
    with pytest.raises(InvalidSquad) as exc:
        build_manual_state(squad([*range(1, 15), 16]), game([f.element(16, team=6, position="MID")]), RULES)
    assert "You need 5 MID (you have 6)." in exc.value.problems
    assert "You need 3 FWD (you have 2)." in exc.value.problems


def test_four_from_one_club_is_rejected():
    # Player 16 is a forward from team 1, which already has players 1, 7 and 13
    extra = [f.element(16, team=1, position="FWD")]
    with pytest.raises(InvalidSquad) as exc:
        build_manual_state(squad([*range(1, 15), 16]), game(extra), RULES)
    assert "At most 3 players from one club (Team 1 has 4)." in exc.value.problems


def test_too_many_free_transfers_is_rejected():
    with pytest.raises(InvalidSquad) as exc:
        build_manual_state(squad(free_transfers=6), game(), RULES)
    assert "Free transfers can't be more than 5." in exc.value.problems
