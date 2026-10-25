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
