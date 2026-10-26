"""The best XI for the next gameweek, whoever you own: a Free Hit squad picked from scratch.

The same optimizer as the recommendations, run for one gameweek with an empty squad, the
season's full budget and unlimited transfers, so it answers "what's the best team money
can buy right now?" under every squad rule (shape, club limit, budget).
"""

from pydantic import BaseModel

from app.game import GameData
from app.optimization.recommend import PickedPlayer, picked_player
from app.optimization.solver import Candidate, Problem, solve
from app.prediction import XPMatrix
from app.rules import POSITIONS, SeasonRules

# Candidates per position: the best by expected points plus the cheapest available.
POOL_BEST = 20
POOL_CHEAPEST = 4


class BestXI(BaseModel):
    model: str
    gameweek: int
    budget: int
    cost: int  # the whole 15-man squad at today's prices
    expected_points: float  # XI + captain bonus
    lineup: list[PickedPlayer]
    bench: list[PickedPlayer]
    captain: PickedPlayer
    vice_captain: PickedPlayer


def best_xi(game: GameData, xp: XPMatrix, rules: SeasonRules) -> BestXI:
    """`xp` must cover at least the next gameweek; only its first gameweek is used."""
    chosen: dict[int, object] = {}
    for pos in POSITIONS:
        pool = [e for e in game.bootstrap.elements if game.position(e) == pos and e.status not in ("u", "n")]
        for e in sorted(pool, key=lambda e: -xp.expected_points[e.id][0])[:POOL_BEST]:
            chosen[e.id] = e
        for e in sorted((e for e in pool if e.status == "a"), key=lambda e: e.now_cost)[:POOL_CHEAPEST]:
            chosen[e.id] = e
    candidates = [
        Candidate(e.id, game.position(e), e.team, e.now_cost, e.now_cost, False, (xp.expected_points[e.id][0],))
        for e in chosen.values()
    ]
    gw = xp.gameweeks[0]
    plan = solve(Problem([gw], candidates, rules.squad.budget, None, rules)).gameweeks[0]
    return BestXI(
        model=xp.model,
        gameweek=gw,
        budget=rules.squad.budget,
        cost=sum(game.players[p].now_cost for p in plan.lineup + plan.bench),
        expected_points=plan.expected_points,
        lineup=[picked_player(game, xp, p, 0) for p in plan.lineup],
        bench=[picked_player(game, xp, p, 0) for p in plan.bench],
        captain=picked_player(game, xp, plan.captain, 0),
        vice_captain=picked_player(game, xp, plan.vice_captain, 0),
    )
