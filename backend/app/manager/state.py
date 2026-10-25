"""ManagerState: everything we know about one manager's situation at the next deadline.

Values that FPL doesn't publish directly are wrapped in Sourced, so the API and UI always
say whether a number came straight from FPL, was derived by us, or was set by the user.
Money is in tenths of £1m.
"""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

Source = Literal["api", "derived", "user_override"]
Position = Literal["GKP", "DEF", "MID", "FWD"]
ChipState = Literal["available", "used", "expired", "upcoming"]


class Sourced(BaseModel, Generic[T]):
    value: T
    source: Source
    note: str | None = None


class SquadPlayer(BaseModel):
    player_id: int
    web_name: str
    team_id: int
    team_short_name: str
    position: Position
    slot: int  # 1-11 starting XI, 12-15 bench in substitution order
    is_captain: bool
    is_vice_captain: bool
    bench_order: int | None  # 1-4 for bench players, None for starters
    now_cost: int
    purchase_price: Sourced[int | None]
    selling_price: Sourced[int]
    status: str
    chance_of_playing_next_round: int | None
    news: str


class ChipStatus(BaseModel):
    chip: str  # FPL's name: wildcard, freehit, bboost, 3xc
    label: str
    half: int
    window_start: int
    window_end: int
    state: ChipState
    played_gameweek: int | None = None
    usable_from_gameweek: int | None = None
    note: str | None = None


class GameweekResult(BaseModel):
    gameweek: int
    points: int
    total_points: int
    overall_rank: int | None
    bank: int
    team_value: int
    transfers: int
    transfer_cost: int
    points_on_bench: int
    chip: str | None


class ManagerState(BaseModel):
    team_id: int
    manager_name: str
    team_name: str
    season: str
    current_gameweek: int
    planning_gameweek: int | None  # the next deadline; None once the season is over
    started_gameweek: int
    overall_rank: int | None
    total_points: int | None

    squad_gameweek: int  # the gameweek whose picks the squad below comes from
    squad_note: str
    squad: list[SquadPlayer]

    bank: Sourced[int]
    team_value: Sourced[int]  # squad at today's prices + bank
    sale_value: Sourced[int]  # bank + estimated selling price of every player
    free_transfers: Sourced[int | None]  # None means unlimited (before a first deadline)
    max_free_transfers: int  # this season's banking cap, so clients needn't hard-code it
    chips: list[ChipStatus]
    past_gameweeks: list[GameweekResult]
    warnings: list[str]
