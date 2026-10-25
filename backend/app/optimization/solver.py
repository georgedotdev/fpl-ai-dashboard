"""The optimization brain: given expected points and the manager's constraints, what's the best plan?

A multi-gameweek integer linear program (solved with HiGHS). Over the planning horizon it
chooses each gameweek's squad, starting XI and captain, and so which transfers to make,
whether to take hits, and when to roll a free transfer instead.

Maximise   sum over gameweeks of  w_t * ( XI points + captain's extra points
                                         + a small weight on bench points
                                         - hit cost x hits )
           + a small value for free transfers still banked at the end of the horizon
where w_t = decay ** t, because predictions further out are less reliable.

Every game rule (squad shape, club limit, XI shape, hit cost, free-transfer cap) comes from
SeasonRules. Injuries aren't special-cased anywhere: they're already in expected points.
Money is in tenths of £1m.
"""

from dataclasses import dataclass, field

import highspy

from app.rules import POSITIONS, SeasonRules

# Small weights on bench players' expected points: they only score through auto-subs.
BENCH_WEIGHT = {"GKP": 0.03, "DEF": 0.1, "MID": 0.1, "FWD": 0.1}
# What a free transfer still banked at the end of the horizon is worth, in points. Without
# it the plan would spend every free transfer in the last week on tiny gains.
FREE_TRANSFER_VALUE = 1.5
DECAY = 0.85
MAX_HITS_PER_GAMEWEEK = 15


@dataclass(frozen=True)
class Candidate:
    player_id: int
    position: str
    team_id: int
    buy_price: int
    sell_price: int  # for owned players, the estimated selling price; otherwise the buy price
    owned: bool
    xp: tuple[float, ...]  # one per planning gameweek


@dataclass(frozen=True)
class Move:
    player_out: int
    player_in: int


@dataclass
class GameweekPlan:
    gameweek: int
    moves: list[Move]
    free_transfers: int | None  # available going into this gameweek; None = unlimited
    hits: int
    lineup: list[int]
    bench: list[int]  # FPL order: goalkeeper first, then outfield by expected points
    captain: int
    vice_captain: int
    expected_points: float  # XI + captain bonus, before hits
    bank: int  # after this gameweek's transfers


@dataclass
class Plan:
    gameweeks: list[GameweekPlan]
    expected_points: float  # over the horizon, minus hit costs, undiscounted
    objective: float  # what the solver maximised (discounted)


@dataclass
class Problem:
    gameweeks: list[int]
    candidates: list[Candidate]
    bank: int
    free_transfers: int | None
    rules: SeasonRules
    decay: float = DECAY
    # Sets of first-gameweek purchases the solver may not choose again, to find alternative
    # plans. An empty set means "not rolling the transfer again".
    excluded_first_buys: list[frozenset[int]] = field(default_factory=list)
    no_transfers: bool = False
    time_limit_s: float = 20.0


class Infeasible(Exception):
    pass


def solve(problem: Problem) -> Plan:
    rules = problem.rules
    cands = problem.candidates
    T = range(len(problem.gameweeks))
    P = range(len(cands))
    cap = rules.transfers.max_banked
    hit_cost = rules.transfers.hit_cost
    weight = [problem.decay**t for t in T]

    h = highspy.Highs()
    h.silent()
    h.setOptionValue("time_limit", problem.time_limit_s)
    h.setOptionValue("mip_rel_gap", 1e-4)

    x = {(p, t): h.addBinary() for p in P for t in T}  # in squad
    lin = {(p, t): h.addBinary() for p in P for t in T}  # in starting XI
    cap_ = {(p, t): h.addBinary() for p in P for t in T}  # captain
    buy = {(p, t): h.addBinary() for p in P for t in T}
    sell = {(p, t): h.addBinary() for p in P for t in T}
    ft = [h.addIntegral(lb=0, ub=MAX_HITS_PER_GAMEWEEK) for _ in range(len(T) + 1)]  # available at t
    hits = [h.addIntegral(lb=0, ub=MAX_HITS_PER_GAMEWEEK) for _ in T]
    left = [h.addIntegral(lb=0, ub=MAX_HITS_PER_GAMEWEEK) for _ in T]  # unused free transfers after t
    took_hits = [h.addBinary() for _ in T]
    bank = [h.addVariable(lb=0, ub=10_000) for _ in T]
    S = h.qsum

    for t in T:
        for p in P:
            before = (1 if cands[p].owned else 0) if t == 0 else x[p, t - 1]
            h.addConstr(x[p, t] == before + buy[p, t] - sell[p, t])
            h.addConstr(buy[p, t] + sell[p, t] <= 1)
            h.addConstr(lin[p, t] <= x[p, t])
            h.addConstr(cap_[p, t] <= lin[p, t])
            if problem.no_transfers:
                h.addConstr(buy[p, t] == 0)

        for pos in POSITIONS:
            in_pos = [p for p in P if cands[p].position == pos]
            h.addConstr(S(x[p, t] for p in in_pos) == rules.squad.positions[pos])
            h.addConstr(S(lin[p, t] for p in in_pos) >= rules.squad.starting_min[pos])
            h.addConstr(S(lin[p, t] for p in in_pos) <= rules.squad.starting_max[pos])
        for team in {c.team_id for c in cands}:
            h.addConstr(S(x[p, t] for p in P if cands[p].team_id == team) <= rules.squad.max_per_club)
        h.addConstr(S(lin[p, t] for p in P) == rules.squad.starting_size)
        h.addConstr(S(cap_[p, t] for p in P) == 1)

        previous_bank = problem.bank if t == 0 else bank[t - 1]
        h.addConstr(
            bank[t]
            == previous_bank
            + S(cands[p].sell_price * sell[p, t] for p in P)
            - S(cands[p].buy_price * buy[p, t] for p in P)
        )

        # Free transfers: left - hits == available - made, and only one of left/hits is non-zero,
        # so hits are exactly the transfers beyond the free ones (no paying to bank transfers).
        made = S(buy[p, t] for p in P)
        h.addConstr(left[t] - hits[t] == ft[t] - made)
        h.addConstr(left[t] <= MAX_HITS_PER_GAMEWEEK * (1 - took_hits[t]))
        h.addConstr(hits[t] <= MAX_HITS_PER_GAMEWEEK * took_hits[t])
        h.addConstr(ft[t + 1] <= left[t] + rules.transfers.free_per_gameweek)
        h.addConstr(ft[t + 1] <= cap)

    if problem.free_transfers is None:
        # Before a manager's first deadline transfers are unlimited; one free transfer after.
        h.addConstr(ft[0] == MAX_HITS_PER_GAMEWEEK)
        h.addConstr(ft[1] <= rules.transfers.free_per_gameweek)
    else:
        h.addConstr(ft[0] == problem.free_transfers)

    for ins in problem.excluded_first_buys:
        chosen = S(buy[p, 0] for p in P if cands[p].player_id in ins)
        others = S(buy[p, 0] for p in P if cands[p].player_id not in ins)
        h.addConstr(chosen - others <= len(ins) - 1)

    objective = S(
        weight[t]
        * (
            S(cands[p].xp[t] * (lin[p, t] + cap_[p, t]) for p in P)
            + S(BENCH_WEIGHT[cands[p].position] * cands[p].xp[t] * (x[p, t] - lin[p, t]) for p in P)
            - hit_cost * hits[t]
        )
        for t in T
    ) + FREE_TRANSFER_VALUE * problem.decay ** len(T) * ft[len(T)]
    # A negligible reward for every banked free transfer, so the solver reports the true
    # count each week rather than any value below it (which would score the same).
    objective += 1e-3 * S(ft)
    h.maximize(objective)

    status = h.getModelStatus()
    has_solution = h.getInfo().primal_solution_status == highspy.SolutionStatus.kSolutionStatusFeasible
    if status not in (highspy.HighsModelStatus.kOptimal, highspy.HighsModelStatus.kTimeLimit) or not has_solution:
        raise Infeasible(f"No valid plan found ({h.modelStatusToString(h.getModelStatus())}).")

    def on(var) -> bool:
        return h.val(var) > 0.5

    plans = []
    for t, gw in enumerate(problem.gameweeks):
        ins = [cands[p] for p in P if on(buy[p, t])]
        outs = [cands[p] for p in P if on(sell[p, t])]
        lineup = [cands[p] for p in P if on(lin[p, t])]
        bench = [cands[p] for p in P if on(x[p, t]) and not on(lin[p, t])]
        captain = next(cands[p] for p in P if on(cap_[p, t]))
        others = sorted((c for c in lineup if c is not captain), key=lambda c: -c.xp[t])
        bench.sort(key=lambda c: (c.position != "GKP", -c.xp[t]))
        plans.append(
            GameweekPlan(
                gameweek=gw,
                moves=_pair_moves(outs, ins),
                free_transfers=None if (t == 0 and problem.free_transfers is None) else round(h.val(ft[t])),
                hits=round(h.val(hits[t])),
                lineup=[c.player_id for c in sorted(lineup, key=lambda c: (POSITIONS.index(c.position), -c.xp[t]))],
                bench=[c.player_id for c in bench],
                captain=captain.player_id,
                vice_captain=others[0].player_id,
                expected_points=round(sum(c.xp[t] for c in lineup) + captain.xp[t], 2),
                bank=round(h.val(bank[t])),
            )
        )
    total = sum(g.expected_points - hit_cost * g.hits for g in plans)
    return Plan(gameweeks=plans, expected_points=round(total, 2), objective=round(h.getInfo().objective_function_value, 3))


def _pair_moves(outs: list[Candidate], ins: list[Candidate]) -> list[Move]:
    """Pair sales with purchases in the same position (the squad shape forces this to balance)."""
    moves = []
    for pos in POSITIONS:
        o = sorted((c for c in outs if c.position == pos), key=lambda c: -c.sell_price)
        i = sorted((c for c in ins if c.position == pos), key=lambda c: -c.buy_price)
        moves += [Move(a.player_id, b.player_id) for a, b in zip(o, i)]
    return moves
