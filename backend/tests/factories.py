"""Small, hand-checkable FPL payloads for tests.

Each helper returns a validated model built from a raw dict shaped like the real API, with
only as many players/gameweeks as a test needs. Keyword arguments override defaults.
"""

from datetime import UTC, datetime, timedelta

from app.fpl.models import (
    Bootstrap,
    ChipPlay,
    ElementSummary,
    Entry,
    EntryGameweek,
    EntryHistory,
    EntryPicks,
    Transfer,
)

SEASON_START = datetime(2026, 8, 21, 17, 30, tzinfo=UTC)
POSITION_IDS = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}


def element(id: int, team: int = 1, position: str = "MID", now_cost: int = 50, **kw) -> dict:
    return {
        "id": id,
        "code": 10_000 + id,
        "web_name": f"Player{id}",
        "first_name": "First",
        "second_name": f"Player{id}",
        "team": team,
        "element_type": POSITION_IDS[position],
        "now_cost": now_cost,
        "cost_change_event": 0,
        "cost_change_start": 0,
        "status": "a",
        "chance_of_playing_next_round": None,
        "chance_of_playing_this_round": None,
        "news": "",
        "form": "3.0",
        "points_per_game": "3.5",
        "total_points": 20,
        "selected_by_percent": "5.0",
        "ep_next": "3.0",
        "ep_this": "3.0",
        "minutes": 450,
        "transfers_in_event": 0,
        "transfers_out_event": 0,
    } | kw


def team(id: int) -> dict:
    return {
        "id": id,
        "code": 100 + id,
        "name": f"Team {id}",
        "short_name": f"T{id:02d}",
        "strength": 3,
        "strength_overall_home": 1100,
        "strength_overall_away": 1100,
        "strength_attack_home": 1100,
        "strength_attack_away": 1100,
        "strength_defence_home": 1100,
        "strength_defence_away": 1100,
    }


def events(current: int, total: int = 38) -> list[dict]:
    return [
        {
            "id": gw,
            "name": f"Gameweek {gw}",
            "deadline_time": (SEASON_START + timedelta(weeks=gw - 1)).isoformat(),
            "finished": gw < current,
            "data_checked": gw < current,
            "is_previous": gw == current - 1,
            "is_current": gw == current,
            "is_next": gw == current + 1,
        }
        for gw in range(1, total + 1)
    ]


ELEMENT_TYPES = [
    {"id": 1, "singular_name_short": "GKP", "squad_select": 2, "squad_min_play": 1, "squad_max_play": 1},
    {"id": 2, "singular_name_short": "DEF", "squad_select": 5, "squad_min_play": 3, "squad_max_play": 5},
    {"id": 3, "singular_name_short": "MID", "squad_select": 5, "squad_min_play": 2, "squad_max_play": 5},
    {"id": 4, "singular_name_short": "FWD", "squad_select": 3, "squad_min_play": 1, "squad_max_play": 3},
]

API_CHIPS = [
    {"id": i, "name": name, "number": 1, "start_event": start, "stop_event": stop, "chip_type": "x"}
    for i, (name, start, stop) in enumerate(
        [
            ("wildcard", 2, 19), ("freehit", 2, 19), ("bboost", 1, 19), ("3xc", 1, 19),
            ("wildcard", 20, 38), ("freehit", 20, 38), ("bboost", 20, 38), ("3xc", 20, 38),
        ],
        start=1,
    )
]

GAME_SETTINGS = {
    "squad_squadplay": 11,
    "squad_squadsize": 15,
    "squad_team_limit": 3,
    "squad_total_spend": 1000,
    "transfers_sell_on_fee": 0.5,
    "max_extra_free_transfers": 4,
}


def standard_squad_elements() -> list[dict]:
    """15 players, ids 1-15: 2 GKP, 5 DEF, 5 MID, 3 FWD spread over teams 1-6, £5.0m each."""
    layout = ["GKP"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    return [element(i, team=(i - 1) % 6 + 1, position=pos) for i, pos in enumerate(layout, start=1)]


def bootstrap(
    elements: list[dict] | None = None,
    current: int = 8,
    chips: list[dict] | None = None,
    game_settings: dict | None = None,
    element_types: list[dict] | None = None,
) -> Bootstrap:
    return Bootstrap.model_validate(
        {
            "elements": standard_squad_elements() if elements is None else elements,
            "teams": [team(i) for i in range(1, 21)],
            "events": events(current),
            "element_types": ELEMENT_TYPES if element_types is None else element_types,
            "chips": API_CHIPS if chips is None else chips,
            "game_settings": GAME_SETTINGS if game_settings is None else game_settings,
        }
    )


def gw_row(event: int, transfers: int = 0, cost: int = 0, bank: int = 0, value: int = 1000, points: int = 50) -> dict:
    return {
        "event": event,
        "points": points,
        "total_points": points * event,
        "overall_rank": 100_000,
        "bank": bank,
        "value": value,
        "event_transfers": transfers,
        "event_transfers_cost": cost,
        "points_on_bench": 0,
    }


def history(rows: list[dict], chips: dict[int, str] | None = None) -> EntryHistory:
    """`chips` maps gameweek -> chip name played that gameweek."""
    return EntryHistory.model_validate(
        {
            "current": rows,
            "chips": [
                {"name": name, "event": gw, "time": (SEASON_START + timedelta(weeks=gw - 1)).isoformat()}
                for gw, name in sorted((chips or {}).items())
            ],
            "past": [],
        }
    )


def chip_plays(chips: dict[int, str]) -> list[ChipPlay]:
    return history([], chips).chips


def transfer(element_in: int, cost_in: int, element_out: int, event: int, cost_out: int = 50) -> Transfer:
    return Transfer.model_validate(
        {
            "element_in": element_in,
            "element_in_cost": cost_in,
            "element_out": element_out,
            "element_out_cost": cost_out,
            "event": event,
            "time": (SEASON_START + timedelta(weeks=event - 1, days=-1)).isoformat(),
        }
    )


def entry(id: int = 42, started_event: int = 1, current_event: int | None = 8) -> Entry:
    return Entry.model_validate(
        {
            "id": id,
            "name": "Test FC",
            "player_first_name": "Ada",
            "player_last_name": "Lovelace",
            "started_event": started_event,
            "current_event": current_event,
            "summary_overall_points": 400,
            "summary_overall_rank": 100_000,
        }
    )


def picks(element_ids: list[int], event: int, captain: int | None = None, vice: int | None = None,
          active_chip: str | None = None, bank: int = 0, value: int = 1000) -> EntryPicks:
    captain = element_ids[0] if captain is None else captain
    vice = element_ids[1] if vice is None else vice
    return EntryPicks.model_validate(
        {
            "active_chip": active_chip,
            "entry_history": gw_row(event, bank=bank, value=value),
            "picks": [
                {
                    "element": el,
                    "position": slot,
                    "multiplier": (2 if el == captain else 1) if slot <= 11 else 0,
                    "is_captain": el == captain,
                    "is_vice_captain": el == vice,
                }
                for slot, el in enumerate(element_ids, start=1)
            ],
        }
    )


def element_summary(prices_by_round: dict[int, int]) -> ElementSummary:
    return ElementSummary.model_validate(
        {
            "history": [
                {
                    "fixture": rnd,
                    "round": rnd,
                    "value": price,
                    "total_points": 2,
                    "minutes": 90,
                    "was_home": True,
                    "opponent_team": 2,
                }
                for rnd, price in sorted(prices_by_round.items())
            ]
        }
    )


__all__ = [
    "EntryGameweek", "bootstrap", "chip_plays", "element", "element_summary", "entry",
    "gw_row", "history", "picks", "standard_squad_elements", "team", "transfer",
]
