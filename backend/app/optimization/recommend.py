"""Turn a manager's state and the expected-points matrix into ranked, readable plans.

This is the glue between the two brains: it builds the optimizer's candidate pool, solves
for the best plan plus a few alternatives and a "no transfers" reference, and attaches the
facts behind each move (expected points, fixtures, availability, prices) so the UI, and
later the explanation layer, can say *why* without computing anything.
"""

from pydantic import BaseModel

from app.game import GameData
from app.manager.state import ManagerState, Sourced
from app.optimization.solver import DECAY, Candidate, ChipOption, Infeasible, Plan, Problem, chip_cost, solve
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
    fixture_difficulty: list[list[int]]  # FPL's 1-5 rating for each of those fixtures


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
    fixtures: list[str]  # this gameweek's fixtures, e.g. ["BHA (H)"]
    price: int
    status: str
    chance_of_playing_next_round: int | None
    news: str
    selected_by_percent: float


class GameweekRecommendation(BaseModel):
    gameweek: int
    free_transfers: int | None
    hits: int
    hit_points: int  # points deducted for hits
    chip: str | None  # label of the chip played this gameweek, e.g. "Bench Boost"
    moves: list[MovePlan]
    captain: PickedPlayer
    vice_captain: PickedPlayer
    lineup: list[PickedPlayer]
    bench: list[PickedPlayer]  # in substitution order, goalkeeper first
    expected_points: float  # XI + captain bonus (+ chip effects), before hits
    bank: int


class ChipAdvice(BaseModel):
    chip: str  # FPL's name
    label: str
    half: int
    window_start: int
    window_end: int
    play_in_gameweek: int | None  # where the best plan plays it within the horizon, if anywhere
    expected_gain: float | None  # best plan's points minus the best plan without this chip
    opportunity_cost: float  # what playing it in the first planning gameweek gives up
    advice: str


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
    no_transfers_expected_points: float  # no transfers and no chips
    # The squad as it stands (before any recommended move), in FPL's slot order: 1-11 the XI,
    # 12-15 the bench; with each player's expected points for the first planning gameweek.
    current: list[PickedPlayer]
    current_captain: int | None
    current_vice_captain: int | None
    plans: list[RecommendedPlan]
    chips: list[ChipAdvice]
    notes: list[str]


def picked_player(game: GameData, xp: XPMatrix, pid: int, t: int) -> PickedPlayer:
    """A player as shown on the pitch for planning gameweek index t."""
    e = game.players[pid]
    return PickedPlayer(
        player_id=pid,
        web_name=e.web_name,
        position=game.position(e),
        team_short_name=game.teams[e.team].short_name,
        xp=xp.expected_points[pid][t],
        fixtures=[
            f"{game.teams[f.opponent].short_name} ({'H' if f.home else 'A'})"
            for f in game.team_fixtures(e.team, xp.gameweeks[t])
        ],
        price=e.now_cost,
        status=e.status,
        chance_of_playing_next_round=e.chance_of_playing_next_round,
        news=e.news,
        selected_by_percent=e.selected_by_percent,
    )


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
    state: ManagerState, game: GameData, xp: XPMatrix, rules: SeasonRules, alternatives: int = 1
) -> Recommendations:
    candidates = build_candidates(state, game, xp)
    by_id = {c.player_id: c for c in candidates}
    chips = chip_options(state, xp.gameweeks)
    labels = rules.chips.labels

    def problem(**kw) -> Problem:
        kw.setdefault("chips", chips)
        return Problem(xp.gameweeks, candidates, state.bank.value, state.free_transfers.value, rules, **kw)

    hold = solve(problem(no_transfers=True, chips=[]))
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
            fixture_difficulty=[[f.difficulty for f in game.team_fixtures(e.team, gw)] for gw in xp.gameweeks],
        )

    def picked(pid: int, t: int) -> PickedPlayer:
        return picked_player(game, xp, pid, t)

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
                    hit_points=g.hits * rules.transfers.hit_cost,
                    chip=labels.get(g.chip.rsplit("-", 1)[0]) if g.chip else None,
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

    best = plans[0]

    def chip_gain(key: str) -> float:
        """Expected points the chip adds to the best plan."""
        t, g = next((t, g) for t, g in enumerate(best.gameweeks) if g.chip == key)
        name = key.rsplit("-", 1)[0]
        if name in rules.chips.captain_bonus_chips:
            return by_id[g.captain].xp[t]
        if name in rules.chips.bench_boost_chips:
            return sum(by_id[p].xp[t] for p in g.bench)
        # Wildcard / Free Hit change the whole plan: compare with the best plan without it.
        return best.expected_points - solve(problem(chips=[c for c in chips if c.key != key])).expected_points

    advice = chip_advice(chips, state, best, chip_gain, xp.gameweeks, labels)

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
        current=[picked_player(game, xp, p.player_id, 0) for p in sorted(state.squad, key=lambda p: p.slot)],
        current_captain=next((p.player_id for p in state.squad if p.is_captain), None),
        current_vice_captain=next((p.player_id for p in state.squad if p.is_vice_captain), None),
        plans=out,
        chips=advice,
        notes=notes,
    )


def chip_options(state: ManagerState, gameweeks: list[int]) -> list[ChipOption]:
    """The chips the manager still holds that can be played somewhere in the horizon."""
    if not gameweeks:
        return []
    options = []
    for c in state.chips:
        if c.state not in ("available", "upcoming") or c.usable_from_gameweek is None:
            continue
        first = c.usable_from_gameweek
        if first <= gameweeks[-1] and c.window_end >= gameweeks[0]:
            options.append(ChipOption(f"{c.chip}-{c.half}", c.chip, first, c.window_end))
    return options


def chip_advice(
    chips: list[ChipOption],
    state: ManagerState,
    best: Plan,
    chip_gain,
    gameweeks: list[int],
    labels: dict[str, str],
) -> list[ChipAdvice]:
    """One line per chip still held: play it now, pencil it in, or save it, and why."""
    played = {g.chip: g.gameweek for g in best.gameweeks if g.chip}
    by_key = {c.key: c for c in chips}
    out = []
    for status in state.chips:
        if status.state not in ("available", "upcoming"):
            continue
        key = f"{status.chip}-{status.half}"
        label = labels.get(status.chip, status.chip)
        option = by_key.get(key)
        gw = played.get(key)
        gain = None
        if gw is not None:
            gain = round(chip_gain(key), 2)
            when = "this gameweek" if gw == gameweeks[0] else f"in GW{gw}"
            if status.window_end == gw:
                why = f"it expires after GW{gw}"
            else:
                why = f"more than the ~{chip_cost(option, gw):.1f} that saving it is likely to be worth"
            advice = f"Play it {when}: about {gain:+.1f} expected points, {why}."
        elif option is None:
            advice = f"Not playable in GW{gameweeks[0]}–{gameweeks[-1]}; its window is GW{status.usable_from_gameweek}–{status.window_end}."
        else:
            advice = (
                f"Save it: no week in GW{gameweeks[0]}–{gameweeks[-1]} beats keeping it for later in its "
                f"window (until GW{status.window_end})."
            )
        out.append(
            ChipAdvice(
                chip=status.chip,
                label=label,
                half=status.half,
                window_start=status.window_start,
                window_end=status.window_end,
                play_in_gameweek=gw,
                expected_gain=gain,
                opportunity_cost=round(chip_cost(option, gameweeks[0]), 2) if option and option.first_gameweek <= gameweeks[0] else 0.0,
                advice=advice,
            )
        )
    return out


def _headline(first: GameweekRecommendation) -> str:
    parts = []
    if first.chip:
        parts.append(f"Play {first.chip}")
    if first.moves:
        names = ", ".join(f"{m.player_out.web_name} → {m.player_in.web_name}" for m in first.moves)
        parts.append(names + (f" (−{first.hit_points} hit)" if first.hits else ""))
    if parts:
        return "; ".join(parts)
    return "Roll your free transfer" if first.free_transfers else "No transfers this week"
