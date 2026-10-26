"""A ManagerState from a squad the manager enters by hand: no team ID needed.

The FPL app doesn't show team IDs, so this is the way in for anyone who can't find theirs.
The manager picks their 15 players and tells us their bank, free transfers and which chips
they still have. Everything else comes from live game data. What we can't know (purchase
prices, so exact selling prices) is labelled as an estimate.
"""

from collections import Counter

from pydantic import BaseModel, Field

from app.game import GameData
from app.manager.builder import NoSquadYet
from app.manager.state import ChipStatus, ManagerState, Sourced, SquadPlayer
from app.rules import POSITIONS, SeasonRules
from app.rules.checks import check_against_bootstrap, chip_windows


class ManualSquad(BaseModel):
    player_ids: list[int] = Field(description="Your 15 players' FPL ids")
    bank: int = Field(ge=0, description="Money in the bank, in tenths of £1m (e.g. 15 for £1.5m)")
    free_transfers: int = Field(ge=0, description="Free transfers you have for the next deadline")
    chips_available: list[str] = Field(
        default_factory=list,
        description='Chips you still have in the current half, as "<chip>-<half>", e.g. "wildcard-1"',
    )


class InvalidSquad(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def validate(squad: ManualSquad, game: GameData, rules: SeasonRules) -> list[str]:
    problems = []
    ids = squad.player_ids
    if len(ids) != rules.squad.size:
        problems.append(f"Pick exactly {rules.squad.size} players (you have {len(ids)}).")
    duplicates = [pid for pid, n in Counter(ids).items() if n > 1]
    if duplicates:
        problems.append("Each player can only be picked once.")
    unknown = [pid for pid in ids if pid not in game.players]
    if unknown:
        problems.append(f"Unknown player id(s): {', '.join(map(str, unknown))}.")
    known = [game.players[pid] for pid in set(ids) if pid in game.players]

    by_position = Counter(game.position(p) for p in known)
    for pos in POSITIONS:
        need = rules.squad.positions[pos]
        if by_position[pos] != need:
            problems.append(f"You need {need} {pos} (you have {by_position[pos]}).")
    by_club = Counter(p.team for p in known)
    for team_id, n in by_club.items():
        if n > rules.squad.max_per_club:
            problems.append(
                f"At most {rules.squad.max_per_club} players from one club "
                f"({game.teams[team_id].name} has {n})."
            )
    if squad.free_transfers > rules.transfers.max_banked:
        problems.append(f"Free transfers can't be more than {rules.transfers.max_banked}.")
    return problems


def build_manual_state(squad: ManualSquad, game: GameData, rules: SeasonRules) -> ManagerState:
    problems = validate(squad, game, rules)
    if problems:
        raise InvalidSquad(problems)
    current, upcoming = game.bootstrap.current_event(), game.bootstrap.next_event()
    if current is None or upcoming is None:
        raise NoSquadYet("There's no upcoming deadline to plan for.")
    planning_gw = upcoming.id

    # A placeholder XI in the squad's own order (the recommendations choose the real one):
    # the first goalkeeper, then outfielders up to the season's minimum formation, filled to 11.
    players = [game.players[pid] for pid in squad.player_ids]
    ordered = sorted(players, key=lambda p: POSITIONS.index(game.position(p)))
    starters: list = []
    for pos in POSITIONS:
        of_pos = [p for p in ordered if game.position(p) == pos]
        starters += of_pos[: rules.squad.starting_min[pos]]
    for p in ordered:
        if len(starters) >= rules.squad.starting_size:
            break
        pos = game.position(p)
        if p not in starters and sum(game.position(s) == pos for s in starters) < rules.squad.starting_max[pos]:
            starters.append(p)
    bench = sorted((p for p in ordered if p not in starters), key=lambda p: game.position(p) != "GKP")

    sell_note = "Entered by hand, so this is today's price. Your real selling price may be lower: FPL keeps half of any rise."
    squad_players = [
        SquadPlayer(
            player_id=p.id,
            web_name=p.web_name,
            team_id=p.team,
            team_short_name=game.teams[p.team].short_name,
            position=game.position(p),
            slot=slot,
            is_captain=False,
            is_vice_captain=False,
            bench_order=slot - rules.squad.starting_size if slot > rules.squad.starting_size else None,
            now_cost=p.now_cost,
            purchase_price=Sourced(value=None, source="derived", note="Unknown for a squad entered by hand."),
            selling_price=Sourced(value=p.now_cost, source="derived", note=sell_note),
            status=p.status,
            chance_of_playing_next_round=p.chance_of_playing_next_round,
            news=p.news,
        )
        for slot, p in enumerate(starters + bench, start=1)
    ]

    return ManagerState(
        team_id=0,
        manager_name="You",
        team_name="Your squad (entered by hand)",
        season=rules.season,
        current_gameweek=current.id,
        planning_gameweek=planning_gw,
        started_gameweek=current.id,
        overall_rank=None,
        total_points=None,
        squad_gameweek=current.id,
        squad_note=(
            "Entered by hand. The starting XI shown is a placeholder; "
            "the recommendations pick your best XI and captain."
        ),
        squad=squad_players,
        bank=Sourced(value=squad.bank, source="user_override", note="Entered by you."),
        team_value=Sourced(
            value=squad.bank + sum(p.now_cost for p in players),
            source="api",
            note="Squad at today's prices plus bank.",
        ),
        sale_value=Sourced(
            value=squad.bank + sum(p.now_cost for p in players),
            source="derived",
            note="Assumes you'd sell everyone at today's prices; your real budget may be a little lower.",
        ),
        free_transfers=Sourced(value=squad.free_transfers, source="user_override", note="Entered by you."),
        max_free_transfers=rules.transfers.max_banked,
        chips=_chips(squad, game, rules, planning_gw),
        past_gameweeks=[],
        warnings=[f"Rules check: {w}" for w in check_against_bootstrap(rules, game.bootstrap)],
    )


def _chips(squad: ManualSquad, game: GameData, rules: SeasonRules, planning_gw: int) -> list[ChipStatus]:
    held = set(squad.chips_available)
    out = []
    for w in chip_windows(rules, game.bootstrap):
        key = f"{w.name}-{w.half}"
        base = dict(
            chip=w.name, label=rules.chips.labels.get(w.name, w.name), half=w.half,
            window_start=w.start, window_end=w.end,
        )
        if w.end < planning_gw:
            out.append(ChipStatus(**base, state="expired"))
        elif w.start > planning_gw:
            # Not open yet, so it can't have been played: every manager still has it.
            out.append(ChipStatus(**base, state="upcoming", usable_from_gameweek=w.start))
        elif key in held:
            out.append(ChipStatus(**base, state="available", usable_from_gameweek=planning_gw))
        else:
            out.append(ChipStatus(**base, state="used", note="Marked as used by you."))
    return out
