"""The optimization brain: given expected points and the manager's constraints, what's the best plan?

A multi-gameweek integer linear program (solved with HiGHS). Over the planning horizon it
chooses each gameweek's squad, starting XI and captain, and so which transfers to make,
whether to take hits, when to roll a free transfer instead, and when to play chips.

Maximise   sum over gameweeks of  w_t * ( XI points + captain's extra points
                                         + Triple Captain's extra points
                                         + bench points (small weight, full with Bench Boost)
                                         - hit cost x hits
                                         - opportunity cost of any chip played )
           + a small value for free transfers still banked at the end of the horizon
where w_t = decay ** t, because predictions further out are less reliable.

Chips are decided jointly with transfers:
- Triple Captain / Bench Boost add the captain's points once more / the bench's points.
- Wildcard makes that gameweek's transfers free without using banked free transfers.
- Free Hit gives one gameweek a separate squad (same budget), then reverts to the base squad.
Playing a chip costs its opportunity cost: what saving it for a better week is likely worth.
That cost falls to zero as the chip's window runs out, so an expiring chip gets used.

Every game rule (squad shape, club limit, XI shape, hit cost, free-transfer cap, chip
behaviour) comes from SeasonRules. Injuries aren't special-cased anywhere: they're already
in expected points. Money is in tenths of £1m.
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

# Opportunity cost of playing each chip, in expected points: roughly what it's worth if saved
# for a good week later in its window (a double gameweek for Triple Captain or Bench Boost, a
# blank for Free Hit, a squad overhaul for Wildcard). Hand-set; see DECISIONS.md D-013. The
# best single-gameweek captain is worth about 9-10 xP, so Triple Captain's par sits above that:
# an ordinary week shouldn't trigger it unless the window is closing.
CHIP_PAR = {"3xc": 12.0, "bboost": 12.0, "freehit": 12.0, "wildcard": 20.0}
# The full cost applies while at least this many gameweeks of the chip's window remain after
# the one it's played in; it shrinks linearly to zero in the window's last gameweek.
CHIP_SAVE_WEEKS = 4
BIG_MONEY = 5_000  # an upper bound on any squad value, in tenths of £1m


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
class ChipOption:
    """One chip the manager still holds, e.g. the first-half Bench Boost."""

    key: str  # unique, e.g. "bboost-1"
    name: str  # FPL's name: wildcard, freehit, bboost, 3xc
    first_gameweek: int  # earliest gameweek it can be played
    last_gameweek: int  # its window's last gameweek (may be beyond the horizon)


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
    chip: str | None  # the ChipOption key played this gameweek
    lineup: list[int]  # the XI that plays (the Free Hit squad's, in a Free Hit week)
    bench: list[int]  # FPL order: goalkeeper first, then outfield by expected points
    captain: int
    vice_captain: int
    expected_points: float  # XI + captain bonus (+ chip effects), before hits
    bank: int  # after this gameweek's transfers


@dataclass
class Plan:
    gameweeks: list[GameweekPlan]
    expected_points: float  # over the horizon, minus hit costs, undiscounted
    objective: float  # what the solver maximised (discounted, after chip opportunity costs)


@dataclass
class Problem:
    gameweeks: list[int]
    candidates: list[Candidate]
    bank: int
    free_transfers: int | None
    rules: SeasonRules
    decay: float = DECAY
    chips: list[ChipOption] = field(default_factory=list)
    # Sets of first-gameweek purchases the solver may not choose again, to find alternative
    # plans. An empty set means "not rolling the transfer again".
    excluded_first_buys: list[frozenset[int]] = field(default_factory=list)
    no_transfers: bool = False
    time_limit_s: float = 20.0


class Infeasible(Exception):
    pass


def chip_cost(chip: ChipOption, gameweek: int) -> float:
    """Opportunity cost of playing `chip` in `gameweek` instead of saving it."""
    weeks_left_after = chip.last_gameweek - gameweek
    return CHIP_PAR.get(chip.name, 0.0) * min(1.0, weeks_left_after / CHIP_SAVE_WEEKS)


def solve(problem: Problem) -> Plan:
    rules = problem.rules
    cr = rules.chips
    cands = problem.candidates
    gws = problem.gameweeks
    T = range(len(gws))
    P = range(len(cands))
    cap = rules.transfers.max_banked
    hit_cost = rules.transfers.hit_cost
    weight = [problem.decay**t for t in T]
    M = MAX_HITS_PER_GAMEWEEK

    h = highspy.Highs()
    h.silent()
    h.setOptionValue("time_limit", problem.time_limit_s)
    h.setOptionValue("mip_rel_gap", 1e-4)
    S = h.qsum

    # --- chips: use[key, t] = 1 if that chip is played in gameweek t ----------------------
    use = {
        (c.key, t): h.addBinary()
        for c in problem.chips
        for t in T
        if c.first_gameweek <= gws[t] <= c.last_gameweek
    }

    def chip_flag(names: list[str], t: int):
        terms = [use[c.key, t] for c in problem.chips if c.name in names and (c.key, t) in use]
        return S(terms) if terms else None

    wildcard_names = [n for n in cr.free_transfer_chips if n not in cr.reverting_chips]
    wc = [chip_flag(wildcard_names, t) for t in T]
    fh = [chip_flag(cr.reverting_chips, t) for t in T]
    tc = [chip_flag(cr.captain_bonus_chips, t) for t in T]
    bb = [chip_flag(cr.bench_boost_chips, t) for t in T]

    # --- squad, team selection and transfers ----------------------------------------------
    x = {(p, t): h.addBinary() for p in P for t in T}  # base squad (what transfers build)
    # The squad that plays: the base squad, except in a Free Hit week, when it's free to differ.
    s = {(p, t): (h.addBinary() if fh[t] is not None else x[p, t]) for p in P for t in T}
    lin = {(p, t): h.addBinary() for p in P for t in T}  # starting XI
    cap_ = {(p, t): h.addBinary() for p in P for t in T}  # captain
    triple = {(p, t): h.addBinary() for p in P for t in T if tc[t] is not None}
    boost = {(p, t): h.addVariable(lb=0, ub=1) for p in P for t in T if bb[t] is not None}
    buy = {(p, t): h.addBinary() for p in P for t in T}
    sell = {(p, t): h.addBinary() for p in P for t in T}
    ft = [h.addIntegral(lb=0, ub=M) for _ in range(len(T) + 1)]  # available going into t
    hits = [h.addIntegral(lb=0, ub=M) for _ in T]
    left = [h.addIntegral(lb=0, ub=M) for _ in T]  # unused free transfers after t
    took_hits = [h.addBinary() for _ in T]
    bank = [h.addVariable(lb=0, ub=BIG_MONEY) for _ in T]

    def squad_rules(var, t):
        for pos in POSITIONS:
            h.addConstr(S(var[p, t] for p in P if cands[p].position == pos) == rules.squad.positions[pos])
        for team in {c.team_id for c in cands}:
            h.addConstr(S(var[p, t] for p in P if cands[p].team_id == team) <= rules.squad.max_per_club)

    for t in T:
        for p in P:
            before = (1 if cands[p].owned else 0) if t == 0 else x[p, t - 1]
            h.addConstr(x[p, t] == before + buy[p, t] - sell[p, t])
            h.addConstr(buy[p, t] + sell[p, t] <= 1)
            if fh[t] is not None:
                # No transfers to the base squad in a Free Hit week; the playing squad equals
                # the base squad unless the Free Hit is played.
                h.addConstr(buy[p, t] + sell[p, t] <= 1 - fh[t])
                h.addConstr(s[p, t] <= x[p, t] + fh[t])
                h.addConstr(s[p, t] >= x[p, t] - fh[t])
            h.addConstr(lin[p, t] <= s[p, t])
            h.addConstr(cap_[p, t] <= lin[p, t])
            if (p, t) in triple:
                h.addConstr(triple[p, t] <= cap_[p, t])
            if (p, t) in boost:
                h.addConstr(boost[p, t] <= s[p, t] - lin[p, t])
                h.addConstr(boost[p, t] <= bb[t])
            if problem.no_transfers:
                h.addConstr(buy[p, t] == 0)

        squad_rules(x, t)
        if fh[t] is not None:
            squad_rules(s, t)
            # The Free Hit squad must be affordable: bank plus selling the whole base squad.
            previous_bank = problem.bank if t == 0 else bank[t - 1]
            previous = [(1 if c.owned else 0) if t == 0 else x[p, t - 1] for p, c in enumerate(cands)]
            h.addConstr(
                S((c.sell_price if c.owned else c.buy_price) * s[p, t] for p, c in enumerate(cands))
                <= previous_bank + S(c.sell_price * previous[p] for p, c in enumerate(cands)) + BIG_MONEY * (1 - fh[t])
            )
        for pos in POSITIONS:
            in_pos = [p for p in P if cands[p].position == pos]
            h.addConstr(S(lin[p, t] for p in in_pos) >= rules.squad.starting_min[pos])
            h.addConstr(S(lin[p, t] for p in in_pos) <= rules.squad.starting_max[pos])
        h.addConstr(S(lin[p, t] for p in P) == rules.squad.starting_size)
        h.addConstr(S(cap_[p, t] for p in P) == 1)
        if tc[t] is not None:
            h.addConstr(S(triple[p, t] for p in P) == tc[t])

        previous_bank = problem.bank if t == 0 else bank[t - 1]
        h.addConstr(
            bank[t]
            == previous_bank
            + S(cands[p].sell_price * sell[p, t] for p in P)
            - S(cands[p].buy_price * buy[p, t] for p in P)
        )

        # Free transfers: left - hits == available - (paid-for transfers), and only one of
        # left/hits is non-zero, so hits are exactly the transfers beyond the free ones.
        made = S(buy[p, t] for p in P)
        if wc[t] is not None:
            # In a Wildcard week every transfer is free and banked transfers are untouched.
            free_made = h.addIntegral(lb=0, ub=M)
            h.addConstr(free_made <= made)
            h.addConstr(free_made <= M * wc[t])
            h.addConstr(free_made >= made - M * (1 - wc[t]))
            h.addConstr(left[t] - hits[t] == ft[t] - made + free_made)
        else:
            h.addConstr(left[t] - hits[t] == ft[t] - made)
        h.addConstr(left[t] <= M * (1 - took_hits[t]))
        h.addConstr(hits[t] <= M * took_hits[t])

        chip_week = [f for f in (wc[t], fh[t]) if f is not None]
        if chip_week and not rules.transfers.chip_weeks.preserve_banked:
            h.addConstr(left[t] <= M * (1 - S(chip_week)))
        gain = rules.transfers.free_per_gameweek
        if chip_week and not rules.transfers.chip_weeks.gains_free_transfer:
            h.addConstr(ft[t + 1] <= left[t] + gain - gain * S(chip_week))
        else:
            h.addConstr(ft[t + 1] <= left[t] + gain)
        h.addConstr(ft[t + 1] <= cap)

        # At most max_per_gameweek chips in any gameweek.
        this_week = [use[c.key, t] for c in problem.chips if (c.key, t) in use]
        if this_week:
            h.addConstr(S(this_week) <= cr.max_per_gameweek)

    for c in problem.chips:
        played = [use[c.key, t] for t in T if (c.key, t) in use]
        if played:
            h.addConstr(S(played) <= 1)
    for name in cr.no_back_to_back:
        for t in T[:-1]:
            pair = [use[c.key, u] for c in problem.chips if c.name == name for u in (t, t + 1) if (c.key, u) in use]
            if len(pair) > 1:
                h.addConstr(S(pair) <= 1)

    if problem.free_transfers is None:
        # Before a manager's first deadline transfers are unlimited; one free transfer after.
        h.addConstr(ft[0] == M)
        h.addConstr(ft[1] <= rules.transfers.free_per_gameweek)
    else:
        h.addConstr(ft[0] == problem.free_transfers)

    for ins in problem.excluded_first_buys:
        chosen = S(buy[p, 0] for p in P if cands[p].player_id in ins)
        others = S(buy[p, 0] for p in P if cands[p].player_id not in ins)
        h.addConstr(chosen - others <= len(ins) - 1)

    def week_value(t: int):
        xp = [cands[p].xp[t] for p in P]
        terms = [
            S(xp[p] * (lin[p, t] + cap_[p, t]) for p in P),
            S(BENCH_WEIGHT[cands[p].position] * xp[p] * (s[p, t] - lin[p, t]) for p in P),
            -hit_cost * hits[t],
        ]
        if tc[t] is not None:
            terms.append(S(xp[p] * triple[p, t] for p in P))
        if bb[t] is not None:
            terms.append(S((1 - BENCH_WEIGHT[cands[p].position]) * xp[p] * boost[p, t] for p in P))
        costs = [chip_cost(c, gws[t]) * use[c.key, t] for c in problem.chips if (c.key, t) in use]
        if costs:
            terms.append(-S(costs))
        return S(terms)

    objective = S(weight[t] * week_value(t) for t in T)
    objective += FREE_TRANSFER_VALUE * problem.decay ** len(T) * ft[len(T)]
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
    for t, gw in enumerate(gws):
        chip = next((c for c in problem.chips if (c.key, t) in use and on(use[c.key, t])), None)
        ins = [cands[p] for p in P if on(buy[p, t])]
        outs = [cands[p] for p in P if on(sell[p, t])]
        lineup = [cands[p] for p in P if on(lin[p, t])]
        bench = [cands[p] for p in P if on(s[p, t]) and not on(lin[p, t])]
        captain = next(cands[p] for p in P if on(cap_[p, t]))
        others = sorted((c for c in lineup if c is not captain), key=lambda c: -c.xp[t])
        bench.sort(key=lambda c: (c.position != "GKP", -c.xp[t]))

        points = sum(c.xp[t] for c in lineup) + captain.xp[t]
        if chip and chip.name in cr.captain_bonus_chips:
            points += captain.xp[t]
        if chip and chip.name in cr.bench_boost_chips:
            points += sum(c.xp[t] for c in bench)
        plans.append(
            GameweekPlan(
                gameweek=gw,
                moves=_pair_moves(outs, ins),
                free_transfers=None if (t == 0 and problem.free_transfers is None) else round(h.val(ft[t])),
                hits=round(h.val(hits[t])),
                chip=chip.key if chip else None,
                lineup=[c.player_id for c in sorted(lineup, key=lambda c: (POSITIONS.index(c.position), -c.xp[t]))],
                bench=[c.player_id for c in bench],
                captain=captain.player_id,
                vice_captain=others[0].player_id,
                expected_points=round(points, 2),
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
