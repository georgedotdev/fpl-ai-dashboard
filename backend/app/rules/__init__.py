"""Per-season FPL game rules, loaded from app/rules/<season>.toml."""

import tomllib
from functools import lru_cache
from importlib import resources

from pydantic import BaseModel

POSITIONS = ("GKP", "DEF", "MID", "FWD")


class SquadRules(BaseModel):
    budget: int
    size: int
    max_per_club: int
    starting_size: int
    positions: dict[str, int]
    starting_min: dict[str, int]
    starting_max: dict[str, int]


class ChipWeekRules(BaseModel):
    preserve_banked: bool
    gains_free_transfer: bool


class TransferRules(BaseModel):
    free_per_gameweek: int
    max_banked: int
    hit_cost: int
    sell_on_fee: float
    extra_free_transfers: dict[int, int]
    chip_weeks: ChipWeekRules


class ChipWindowRule(BaseModel):
    name: str
    half: int
    start: int
    end: int


class ChipRules(BaseModel):
    labels: dict[str, str]
    max_per_gameweek: int
    no_back_to_back: list[str]
    free_transfer_chips: list[str]
    reverting_chips: list[str]
    captain_bonus_chips: list[str]
    bench_boost_chips: list[str]
    windows: list[ChipWindowRule]


class SeasonRules(BaseModel):
    season: str
    verified_on: str
    squad: SquadRules
    transfers: TransferRules
    chips: ChipRules


@lru_cache
def load_rules(season: str) -> SeasonRules:
    """Load rules for a season key such as "2026_27"."""
    text = resources.files("app.rules").joinpath(f"{season}.toml").read_text(encoding="utf-8")
    return SeasonRules.model_validate(tomllib.loads(text))
