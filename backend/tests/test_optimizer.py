"""Optimizer constraints on small squads where the right answer can be worked out by hand.

The owned squad (ids 1-15) is 2 GKP, 5 DEF, 5 MID, 3 FWD, spread so no club has more than
two. Starters score 4 a week, the four weakest score 1, so the natural XI is a 4-4-2. Every
player costs £5.0m. Candidates to buy have ids from 100.
"""

import pytest

from app.optimization.solver import Candidate, Problem, solve
from app.rules import load_rules

RULES = load_rules("2026_27")
LAYOUT = ["GKP"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
WEAK = {2, 7, 12, 15}


def owned(horizon: int = 1, overrides: dict[int, dict] | None = None) -> list[Candidate]:
    squad = []
    for pid, pos in enumerate(LAYOUT, start=1):
        kw = dict(player_id=pid, position=pos, team_id=(pid - 1) % 8 + 1, buy_price=50, sell_price=50,
                  owned=True, xp=(1.0 if pid in WEAK else 4.0,) * horizon)
        kw |= (overrides or {}).get(pid, {})
        squad.append(Candidate(**kw))
    return squad


def target(pid: int, position: str, xp: float, price: int = 50, team: int = 20, horizon: int = 1) -> Candidate:
    return Candidate(pid, position, team, price, price, False, (xp,) * horizon)


def plan_for(candidates, bank=0, ft=1, horizon=1, **kw):
    return solve(Problem(list(range(9, 9 + horizon)), candidates, bank, ft, RULES, **kw))


def test_nothing_better_available_means_roll_the_transfer():
    plan = plan_for(owned() + [target(100, "MID", 3.0)])
    gw = plan.gameweeks[0]
    assert gw.moves == [] and gw.hits == 0
    assert len(gw.lineup) == 11 and len(gw.bench) == 4
    assert set(gw.bench) == WEAK
    assert gw.bench[0] == 2  # bench goalkeeper goes first, as FPL requires
    # 11 starters at 4 + captain's extra 4
    assert gw.expected_points == pytest.approx(48.0)


def test_clear_upgrade_is_made_with_the_free_transfer():
    squad = owned(overrides={8: {"xp": (0.0,)}})  # a starter who won't play
    plan = plan_for(squad + [target(100, "MID", 6.0)])
    gw = plan.gameweeks[0]
    assert [(m.player_out, m.player_in) for m in gw.moves] == [(8, 100)]
    assert gw.hits == 0
    assert gw.captain == 100


def test_budget_is_bank_plus_selling_price():
    # Selling player 8 raises 5.0 (its estimated selling price) + 0.5 bank = 5.5: target costs 6.0
    squad = owned(overrides={8: {"xp": (0.0,), "buy_price": 60, "sell_price": 50}})
    assert plan_for(squad + [target(100, "MID", 9.0, price=60)], bank=5).gameweeks[0].moves == []
    # With 1.0 in the bank it's affordable
    moves = plan_for(squad + [target(100, "MID", 9.0, price=60)], bank=10).gameweeks[0].moves
    assert [(m.player_out, m.player_in) for m in moves] == [(8, 100)]


def test_hits_are_taken_only_when_they_pay_for_themselves():
    squad = owned(overrides={8: {"xp": (0.0,)}, 9: {"xp": (0.0,)}})
    # Second upgrade gains 6 - 0 = 6 > 4-point hit: take it
    plan = plan_for(squad + [target(100, "MID", 6.0), target(101, "MID", 6.0, team=19)])
    assert len(plan.gameweeks[0].moves) == 2 and plan.gameweeks[0].hits == 1
    # Replacements worth 3: the second gains 3 < 4, so only the free one is made
    plan = plan_for(squad + [target(100, "MID", 3.0), target(101, "MID", 3.0, team=19)])
    assert len(plan.gameweeks[0].moves) == 1 and plan.gameweeks[0].hits == 0


def test_no_more_than_three_from_one_club():
    # Team 1 already has players 1 and 9; move player 3 there to make three. They're all
    # strong (8 points), so selling one of them to make room isn't worth it.
    strong = {"xp": (8.0,)}
    squad = owned(overrides={1: strong, 3: {"team_id": 1, **strong}, 9: strong, 8: {"xp": (0.0,)}})
    plan = plan_for(squad + [target(100, "MID", 9.0, team=1), target(101, "MID", 5.0, team=19)])
    assert [(m.player_out, m.player_in) for m in plan.gameweeks[0].moves] == [(8, 101)]


def test_injured_player_kept_when_replacing_isnt_worth_a_hit():
    squad = owned(overrides={8: {"xp": (0.0,)}})
    plan = plan_for(squad + [target(100, "MID", 2.0)], ft=0)
    assert plan.gameweeks[0].moves == []  # 2 points gain < 4-point hit; bench player 12 comes in
    assert 12 in plan.gameweeks[0].lineup and 8 in plan.gameweeks[0].bench


def test_free_transfers_bank_up_to_the_cap():
    plan = plan_for(owned(horizon=3), ft=4, horizon=3)
    assert [g.free_transfers for g in plan.gameweeks] == [4, 5, 5]


def test_formation_rules_hold():
    # Forwards are by far the best players, but at most 3 can start, and only 1 goalkeeper.
    squad = owned(overrides={13: {"xp": (10.0,)}, 14: {"xp": (10.0,)}, 15: {"xp": (10.0,)}, 2: {"xp": (9.0,)}})
    gw = plan_for(squad).gameweeks[0]
    positions = {pid: pos for pid, pos in enumerate(LAYOUT, start=1)}
    starting = [positions[p] for p in gw.lineup]
    assert starting.count("FWD") == 3 and starting.count("GKP") == 1
    assert starting.count("DEF") >= 3 and starting.count("MID") >= 2
    assert gw.captain in (13, 14, 15)
    assert gw.vice_captain in gw.lineup and gw.vice_captain != gw.captain


def test_planning_ahead_saves_a_transfer_for_a_bigger_gain_next_week():
    # Players 8 and 9 are fine in GW9 but out in GW10, when two good replacements are
    # available. Rolling the GW9 transfer makes both GW10 moves free (no hit).
    squad = owned(horizon=2, overrides={8: {"xp": (4.0, 0.0)}, 9: {"xp": (4.0, 0.0)}})
    alts = [target(100, "MID", 0.0, horizon=2), target(101, "MID", 0.0, team=19, horizon=2)]
    alts = [Candidate(a.player_id, a.position, a.team_id, a.buy_price, a.sell_price, False, (0.0, 6.0)) for a in alts]
    plan = plan_for(squad + alts, horizon=2)
    assert plan.gameweeks[0].moves == []
    assert plan.gameweeks[1].free_transfers == 2
    assert len(plan.gameweeks[1].moves) == 2 and plan.gameweeks[1].hits == 0


def test_excluding_a_move_set_finds_the_next_best_plan():
    squad = owned(overrides={8: {"xp": (0.0,)}})
    cands = squad + [target(100, "MID", 6.0), target(101, "MID", 5.0, team=19)]
    first = plan_for(cands).gameweeks[0].moves
    assert [(m.player_out, m.player_in) for m in first] == [(8, 100)]
    second = plan_for(cands, excluded_first_buys=[frozenset({100})]).gameweeks[0].moves
    assert [(m.player_out, m.player_in) for m in second] == [(8, 101)]


def test_no_transfers_mode_holds_the_squad():
    squad = owned(overrides={8: {"xp": (0.0,)}})
    plan = plan_for(squad + [target(100, "MID", 9.0)], no_transfers=True)
    assert plan.gameweeks[0].moves == []


# --- chips ------------------------------------------------------------------------------
# Opportunity cost: the chip's par value while 4+ gameweeks of its window remain after the
# week it's played, shrinking linearly to 0 in the window's last gameweek.

from app.optimization.solver import CHIP_PAR, ChipOption, chip_cost  # noqa: E402


def chip(name: str, last: int, first: int = 1, half: int = 1) -> ChipOption:
    return ChipOption(key=f"{name}-{half}", name=name, first_gameweek=first, last_gameweek=last)


def test_chip_cost_shrinks_as_the_window_closes():
    tc = chip("3xc", last=19)
    assert chip_cost(tc, 9) == CHIP_PAR["3xc"]  # 10 weeks left
    assert chip_cost(tc, 17) == pytest.approx(CHIP_PAR["3xc"] * 2 / 4)
    assert chip_cost(tc, 19) == 0.0  # last chance


def test_expiring_triple_captain_is_played():
    plan = plan_for(owned(), chips=[chip("3xc", last=9)])
    gw = plan.gameweeks[0]
    assert gw.chip == "3xc-1"
    assert gw.expected_points == pytest.approx(11 * 4 + 4 + 4)  # captain counted three times


def test_triple_captain_is_saved_when_a_better_week_is_likely():
    # Captain gain 4 < opportunity cost 10 with ten weeks of the window left
    plan = plan_for(owned(), chips=[chip("3xc", last=19)])
    assert plan.gameweeks[0].chip is None
    assert plan.gameweeks[0].expected_points == pytest.approx(48.0)


def test_triple_captain_goes_to_the_best_week():
    # Player 13 has a 12-point week in GW10. Window ends GW11 (costs 5, 2.5, 0).
    # Net: GW9 4-5 < 0; GW10 (12-2.5) x 0.85 = 8.1; GW11 4 x 0.72 = 2.9 -> GW10
    squad = owned(horizon=3, overrides={13: {"xp": (4.0, 12.0, 4.0)}})
    plan = plan_for(squad, horizon=3, chips=[chip("3xc", last=11)])
    assert [g.chip for g in plan.gameweeks] == [None, "3xc-1", None]
    assert plan.gameweeks[1].captain == 13


def test_one_chip_per_gameweek_and_the_better_one_wins():
    # Bench of four 3-pointers: Bench Boost +12 beats Triple Captain +4
    bench = {"xp": (3.0,)}
    squad = owned(overrides={2: bench, 7: bench, 12: bench, 15: bench})
    plan = plan_for(squad, chips=[chip("3xc", last=9), chip("bboost", last=9)])
    gw = plan.gameweeks[0]
    assert gw.chip == "bboost-1"
    assert gw.expected_points == pytest.approx(11 * 4 + 4 + 4 * 3)


def test_wildcard_makes_a_squad_overhaul_free_and_keeps_banked_transfers():
    # Four starting midfielders are out for both weeks; four 6-point replacements exist.
    out = {"xp": (0.0, 0.0)}
    squad = owned(horizon=2, overrides={8: out, 9: out, 10: out, 11: out})
    targets = [target(100 + i, "MID", 6.0, team=20 - i, horizon=2) for i in range(4)]
    plan = plan_for(squad + targets, ft=1, horizon=2, chips=[chip("wildcard", last=10)])
    gw9, gw10 = plan.gameweeks
    assert gw9.chip == "wildcard-1"
    assert len(gw9.moves) >= 4 and gw9.hits == 0
    assert gw10.free_transfers == 2  # the banked one kept, plus the weekly one


def test_free_hit_plays_a_one_week_squad_then_reverts():
    # Six of the starters blank in GW9 only; six one-week replacements exist.
    blank = {"xp": (0.0, 4.0)}
    squad = owned(horizon=2, overrides={p: blank for p in (3, 4, 5, 6, 8, 9)})
    one_week = [
        Candidate(100 + i, pos, 20 - i, 50, 50, False, (6.0, 1.0))
        for i, pos in enumerate(["DEF", "DEF", "DEF", "DEF", "MID", "MID"])
    ]
    plan = plan_for(squad + one_week, horizon=2, chips=[chip("freehit", last=9)])
    gw9, gw10 = plan.gameweeks
    assert gw9.chip == "freehit-1"
    assert gw9.moves == [] and gw9.hits == 0  # the base squad isn't touched
    assert {100, 101, 102, 103, 104, 105} <= set(gw9.lineup)
    assert gw10.moves == [] and {3, 4, 5, 6, 8, 9} <= set(gw10.lineup)  # reverted
    assert gw10.free_transfers == 2


def test_no_back_to_back_free_hits():
    blank = {"xp": (0.0, 0.0)}
    squad = owned(horizon=2, overrides={p: blank for p in (3, 4, 5, 6, 8, 9)})
    one_week = [
        Candidate(100 + i, pos, 20 - i, 50, 50, False, (6.0, 6.0))
        for i, pos in enumerate(["DEF", "DEF", "DEF", "DEF", "MID", "MID"])
    ]
    chips = [chip("freehit", last=9), ChipOption("freehit-2", "freehit", 10, 38)]
    plan = plan_for(squad + one_week, horizon=2, chips=chips)
    assert sum(g.chip is not None for g in plan.gameweeks) <= 1


def test_chips_are_only_played_inside_their_window():
    plan = plan_for(owned(horizon=2), horizon=2, chips=[ChipOption("3xc-2", "3xc", 20, 20)])
    assert all(g.chip is None for g in plan.gameweeks)
