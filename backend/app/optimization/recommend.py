"""Turn a manager's state and the expected-points matrix into ranked, readable plans.

This is the glue between the two brains: it builds the optimizer's candidate pool, solves
for the best plan plus a few alternatives and a "no transfers" reference, and attaches the
facts behind each move (expected points, fixtures, availability, prices) so the UI, and
later the explanation layer, can say *why* without computing anything.
"""

from pydantic import BaseModel

from app.game import GameData
from app.manager.state import ManagerState, Sourced
from app.optimization.solver import DECAY, Candidate, Infeasible, Plan, Problem, solve
from app.prediction import XPMatrix
from app.rules import POSITIONS, SeasonRules

# Candidate pool per position: the best by discounted expected points, plus the cheapest
# available (budget enablers). Owned players are always included. On live data, widening
# DEF/MID from 15 to 25 gave the identical optimal plan at twice the solve time.
POOL_TOP = {"GKP": 6, "DEF": 15, "MID": 15, "FWD": 10}
POOL_CHEAPEST = 3


class PlayerFacts(BaseModel):
    player_id: int
    web_name: str
    team_short_name: str
    position: str
    price: int  # buy price for players coming in, estimated selling price for players going out
    xp: list[float]  # per planning gameweek
    xp_total: float
    availability: list[float]
    status: str
    news: str
    fixtures: list[list[str]]  # per planning gameweek, e.g. [["MCI (H)"], []] for a blank


class MovePlan(BaseModel):
    player_out: PlayerFacts
    player_in: PlayerFacts
    xp_gain: float  # player_in.xp_total - player_out.xp_total over the horizon


class PickedPlayer(BaseModel):
    player_id: int
    web_name: str
    position: str
    team_short_name: str
    xp: float


class GameweekRecommendation(BaseModel):
    gameweek: int
    free_transfers: int | None
    hits: int
    moves: list[MovePlan]
    captain: PickedPlayer
    vice_captain: PickedPlayer
    lineup: list[PickedPlayer]
    bench: list[PickedPlayer]  # in substitution order, goalkeeper first
    expected_points: float  # XI + captain bonus, before hits
    bank: int


class RecommendedPlan(BaseModel):
    rank: int
    headline: str
    expected_points: float  # over the horizon, after hits
    gain_vs_no_transfers: float
    gameweeks: list[GameweekRecommendation]


class Recommendations(BaseModel):
    team_id: int
    model: str
    gameweeks: list[int]
    decay: float
    bank: Sourced[int]
    free_transfers: Sourced[int | None]
    squad_gameweek: int
    no_transfers_expected_points: float
    plans: list[RecommendedPlan]
    notes: list[str]


def build_candidates(state: ManagerState, game: GameData, xp: XPMatrix) -> list[Candidate]:
    weights = [DECAY**t for t in range(len(xp.gameweeks))]

    def value(pid: int) -> float:
        return sum(w * v for w, v in zip(weights, xp.expected_points[pid]))

    owned = {p.player_id: p for p in state.squad}
    chosen = set(owned)
    for pos in POSITIONS:
        pool = [
            e for e in game.bootstrap.elements
            if game.position(e) == pos and e.id not in owned and e.status not in ("u", "n")
        ]
        chosen.update(e.id for e in sorted(pool, key=lambda e: -value(e.id))[: POOL_TOP[pos]])
        affordable = [e for e in pool if e.status == "a"]
        chosen.update(e.id for e in sorted(affordable, key=lambda e: (e.now_cost, -value(e.id)))[:POOL_CHEAPEST])

    candidates = []
    for pid in sorted(chosen):
        e = game.players[pid]
        mine = owned.get(pid)
        candidates.append(
            Candidate(
                player_id=pid,
                position=game.position(e),
                team_id=e.team,
                buy_price=e.now_cost,
                sell_price=mine.selling_price.value if mine else e.now_cost,
                owned=mine is not None,
                xp=tuple(xp.expected_points[pid]),
            )
        )
    return candidates


def recommend(
    state: ManagerState, game: GameData, xp: XPMatrix, rules: SeasonRules, alternatives: int = 2
) -> Recommendations:
    candidates = build_candidates(state, game, xp)
    by_id = {c.player_id: c for c in candidates}

    def problem(**kw) -> Problem:
        return Problem(xp.gameweeks, candidates, state.bank.value, state.free_transfers.value, rules, **kw)

    hold = solve(problem(no_transfers=True))
    plans: list[Plan] = []
    excluded: list[frozenset[int]] = []
    for attempt in range(1 + alternatives):
        try:
            plan = solve(problem(excluded_first_buys=list(excluded)))
        except Infeasible:
            if attempt == 0:
                raise
            break  # no other valid first move exists; fewer alternatives is fine
        plans.append(plan)
        excluded.append(frozenset(m.player_in for m in plan.gameweeks[0].moves))

    def facts(pid: int, sold: bool) -> PlayerFacts:
        e = game.players[pid]
        c = by_id[pid]
        return PlayerFacts(
            player_id=pid,
            web_name=e.web_name,
            team_short_name=game.teams[e.team].short_name,
            position=c.position,
            price=c.sell_price if sold else c.buy_price,
            xp=list(c.xp),
            xp_total=round(sum(c.xp), 2),
            availability=xp.availability[pid],
            status=e.status,
            news=e.news,
            fixtures=[
                [f"{game.teams[f.opponent].short_name} ({'H' if f.home else 'A'})" for f in game.team_fixtures(e.team, gw)]
                for gw in xp.gameweeks
            ],
        )

    def picked(pid: int, t: int) -> PickedPlayer:
        e = game.players[pid]
        return PickedPlayer(
            player_id=pid, web_name=e.web_name, position=by_id[pid].position,
            team_short_name=game.teams[e.team].short_name, xp=by_id[pid].xp[t],
        )

    out = []
    for rank, plan in enumerate(sorted(plans, key=lambda p: -p.objective), start=1):
        gws = []
        for t, g in enumerate(plan.gameweeks):
            moves = []
            for m in g.moves:
                a, b = facts(m.player_out, sold=True), facts(m.player_in, sold=False)
                moves.append(MovePlan(player_out=a, player_in=b, xp_gain=round(b.xp_total - a.xp_total, 2)))
            gws.append(
                GameweekRecommendation(
                    gameweek=g.gameweek,
                    free_transfers=g.free_transfers,
                    hits=g.hits,
                    moves=moves,
                    captain=picked(g.captain, t),
                    vice_captain=picked(g.vice_captain, t),
                    lineup=[picked(p, t) for p in g.lineup],
                    bench=[picked(p, t) for p in g.bench],
                    expected_points=g.expected_points,
                    bank=g.bank,
                )
            )
        out.append(
            RecommendedPlan(
                rank=rank,
                headline=_headline(gws[0]),
                expected_points=plan.expected_points,
                gain_vs_no_transfers=round(plan.expected_points - hold.expected_points, 2),
                gameweeks=gws,
            )
        )

    notes = [
        f"Expected points come from the '{xp.model}' predictor.",
        f"Later gameweeks count less (x{DECAY} per week) because predictions get less certain.",
        "Prices are assumed not to change over the planning horizon.",
    ]
    if state.free_transfers.source != "api":
        notes.append(
            f"Free transfers ({state.free_transfers.value}) are "
            + ("your correction." if state.free_transfers.source == "user_override" else "derived; correct them if wrong.")
        )
    return Recommendations(
        team_id=state.team_id,
        model=xp.model,
        gameweeks=xp.gameweeks,
        decay=DECAY,
        bank=state.bank,
        free_transfers=state.free_transfers,
        squad_gameweek=state.squad_gameweek,
        no_transfers_expected_points=hold.expected_points,
        plans=out,
        notes=notes,
    )


def _headline(first: GameweekRecommendation) -> str:
    if not first.moves:
        return "Roll your free transfer" if first.free_transfers else "No transfers this week"
    names = ", ".join(f"{m.player_out.web_name} → {m.player_in.web_name}" for m in first.moves)
    hit = f" (−{first.hits * 4} hit)" if first.hits else ""
    return f"{names}{hit}"
