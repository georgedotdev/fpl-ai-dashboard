"""Dashboard views built from game data and expected points: player list, fixture difficulty,
captaincy and best picks. Money is in tenths of £1m."""

from pydantic import BaseModel

from app.game import GameData
from app.prediction import XPMatrix


class PlayerSummary(BaseModel):
    player_id: int
    web_name: str
    team_id: int
    team_short_name: str
    position: str
    now_cost: int
    cost_change_event: int  # price change since this gameweek's deadline
    cost_change_start: int  # price change since the season started
    net_transfers_event: int  # transfers in minus out this gameweek: what drives price changes
    form: float
    total_points: int
    selected_by_percent: float
    status: str
    chance_of_playing_next_round: int | None
    news: str
    ep_next: float | None  # FPL's own estimate (form x chance of playing)
    xp_next: float  # ours, for the next gameweek
    xp_horizon: float  # ours, summed over the horizon
    xp_per_million: float  # xp_horizon per £1m of price
    upcoming: list[str]  # e.g. ["ARS (H)", "MCI (A)"]


class TeamFixtureCell(BaseModel):
    gameweek: int
    opponent: str
    home: bool
    difficulty: int


class TeamTicker(BaseModel):
    team_id: int
    name: str
    short_name: str
    gameweeks: list[list[TeamFixtureCell]]  # per gameweek: none (blank), one, or two (double)
    fixture_count: int
    average_difficulty: float | None


def player_summaries(game: GameData, xp: XPMatrix) -> list[PlayerSummary]:
    gws = xp.gameweeks
    rows = []
    for p in game.bootstrap.elements:
        horizon = round(xp.total(p.id), 2)
        upcoming = []
        for f in (f for gw in gws for f in game.team_fixtures(p.team, gw)):
            upcoming.append(f"{game.teams[f.opponent].short_name} ({'H' if f.home else 'A'})")
        rows.append(
            PlayerSummary(
                player_id=p.id,
                web_name=p.web_name,
                team_id=p.team,
                team_short_name=game.teams[p.team].short_name,
                position=game.position(p),
                now_cost=p.now_cost,
                cost_change_event=p.cost_change_event,
                cost_change_start=p.cost_change_start,
                net_transfers_event=p.transfers_in_event - p.transfers_out_event,
                form=p.form,
                total_points=p.total_points,
                selected_by_percent=p.selected_by_percent,
                status=p.status,
                chance_of_playing_next_round=p.chance_of_playing_next_round,
                news=p.news,
                ep_next=p.ep_next,
                xp_next=xp.expected_points[p.id][0] if gws else 0.0,
                xp_horizon=horizon,
                xp_per_million=round(horizon / (p.now_cost / 10), 2) if p.now_cost else 0.0,
                upcoming=upcoming,
            )
        )
    return rows


def fixture_ticker(game: GameData, gameweeks: list[int]) -> list[TeamTicker]:
    """Every team's fixtures over the gameweeks, easiest run first."""
    tickers = []
    for team in game.bootstrap.teams:
        cells = [
            [
                TeamFixtureCell(
                    gameweek=gw,
                    opponent=game.teams[f.opponent].short_name,
                    home=f.home,
                    difficulty=f.difficulty,
                )
                for f in game.team_fixtures(team.id, gw)
            ]
            for gw in gameweeks
        ]
        difficulties = [c.difficulty for gw in cells for c in gw]
        tickers.append(
            TeamTicker(
                team_id=team.id,
                name=team.name,
                short_name=team.short_name,
                gameweeks=cells,
                fixture_count=len(difficulties),
                average_difficulty=round(sum(difficulties) / len(difficulties), 2) if difficulties else None,
            )
        )
    # More fixtures first (doubles beat blanks), then the easiest average.
    return sorted(tickers, key=lambda t: (-t.fixture_count, t.average_difficulty or 9, t.short_name))
