"""Pydantic models of the raw FPL API responses.

Only the fields we use are declared; anything else FPL sends is ignored. If FPL renames or
drops a declared field, validation fails in the client with a clear FPLSchemaError instead
of a KeyError somewhere deep in the app.

Money is in tenths of £1m throughout, exactly as FPL sends it (now_cost 85 == £8.5m).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _FPLModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


# --- bootstrap-static/ -------------------------------------------------------------


class Element(_FPLModel):
    """A player ("element" in FPL's vocabulary)."""

    id: int
    code: int
    web_name: str
    first_name: str
    second_name: str
    team: int
    element_type: int  # 1 GKP, 2 DEF, 3 MID, 4 FWD
    now_cost: int
    cost_change_event: int
    cost_change_start: int
    status: str  # a available, d doubtful, i injured, s suspended, u unavailable, n not in squad
    chance_of_playing_next_round: int | None
    chance_of_playing_this_round: int | None
    news: str
    form: float
    points_per_game: float
    total_points: int
    selected_by_percent: float
    ep_next: float | None
    ep_this: float | None
    minutes: int
    transfers_in_event: int
    transfers_out_event: int


class Team(_FPLModel):
    id: int
    code: int
    name: str
    short_name: str
    # In 2026/27 FPL sends strength as null and the attack/defence strengths as 0, so none
    # of these can be relied on as model features; fixture difficulty is used instead.
    strength: int | None
    strength_overall_home: int | None
    strength_overall_away: int | None
    strength_attack_home: int | None
    strength_attack_away: int | None
    strength_defence_home: int | None
    strength_defence_away: int | None


class Event(_FPLModel):
    """A gameweek ("event" in FPL's vocabulary)."""

    id: int
    name: str
    deadline_time: datetime
    finished: bool
    data_checked: bool
    is_previous: bool
    is_current: bool
    is_next: bool
    average_entry_score: int | None = None
    highest_score: int | None = None


class ElementType(_FPLModel):
    id: int
    singular_name_short: str  # GKP / DEF / MID / FWD
    squad_select: int
    squad_min_play: int
    squad_max_play: int


class ChipWindow(_FPLModel):
    """One chip and the gameweeks it can be played in (start_event..stop_event inclusive)."""

    id: int
    name: str  # wildcard, freehit, bboost, 3xc
    number: int
    start_event: int
    stop_event: int
    chip_type: str


class GameSettings(_FPLModel):
    squad_squadplay: int
    squad_squadsize: int
    squad_team_limit: int
    squad_total_spend: int
    transfers_sell_on_fee: float
    max_extra_free_transfers: int


class Bootstrap(_FPLModel):
    elements: list[Element]
    teams: list[Team]
    events: list[Event]
    element_types: list[ElementType]
    chips: list[ChipWindow] = []
    game_settings: GameSettings

    def current_event(self) -> Event | None:
        return next((e for e in self.events if e.is_current), None)

    def next_event(self) -> Event | None:
        return next((e for e in self.events if e.is_next), None)


# --- fixtures/ ---------------------------------------------------------------------


class Fixture(_FPLModel):
    id: int
    code: int
    event: int | None  # None while a fixture is postponed and not yet rescheduled
    kickoff_time: datetime | None
    team_h: int
    team_a: int
    team_h_difficulty: int
    team_a_difficulty: int
    team_h_score: int | None
    team_a_score: int | None
    started: bool | None
    finished: bool


# --- entry/{team_id}/... -----------------------------------------------------------


class Entry(_FPLModel):
    id: int
    name: str
    player_first_name: str
    player_last_name: str
    started_event: int
    current_event: int | None
    summary_overall_points: int | None
    summary_overall_rank: int | None


class EntryGameweek(_FPLModel):
    """One gameweek row of entry/{id}/history/ (also the entry_history block of picks)."""

    event: int
    points: int
    total_points: int
    overall_rank: int | None = None
    bank: int
    value: int  # team value at current prices, bank included
    event_transfers: int
    event_transfers_cost: int
    points_on_bench: int


class ChipPlay(_FPLModel):
    name: str
    event: int
    time: datetime


class PastSeason(_FPLModel):
    season_name: str
    total_points: int
    rank: int | None


class EntryHistory(_FPLModel):
    current: list[EntryGameweek]
    chips: list[ChipPlay]
    past: list[PastSeason]


class Pick(_FPLModel):
    element: int
    position: int  # 1-11 starting XI, 12-15 bench in order
    multiplier: int
    is_captain: bool
    is_vice_captain: bool


class EntryPicks(_FPLModel):
    active_chip: str | None
    entry_history: EntryGameweek
    picks: list[Pick]


class Transfer(_FPLModel):
    element_in: int
    element_in_cost: int
    element_out: int
    element_out_cost: int
    event: int
    time: datetime


# --- element-summary/{player_id}/ ----------------------------------------------------


class PlayerFixtureResult(_FPLModel):
    fixture: int
    round: int
    value: int  # the player's price at the time of this fixture
    total_points: int
    minutes: int
    was_home: bool
    opponent_team: int


class ElementSummary(_FPLModel):
    history: list[PlayerFixtureResult]
