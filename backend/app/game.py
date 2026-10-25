"""GameData: the season-wide FPL data (players, teams, gameweeks, fixtures) and helpers on it."""

from collections import defaultdict
from dataclasses import dataclass, field
from functools import cached_property

from app.fpl import FPLClient
from app.fpl.models import Bootstrap, Element, Event, Fixture, Team
from app.rules import POSITIONS


@dataclass(frozen=True)
class TeamFixture:
    """One fixture from one team's point of view."""

    fixture_id: int
    gameweek: int
    opponent: int
    home: bool
    difficulty: int  # FPL's 1 (easy) to 5 (hard), for this team


@dataclass
class GameData:
    bootstrap: Bootstrap
    fixtures: list[Fixture]
    _cache: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, client: FPLClient) -> "GameData":
        return cls(client.bootstrap(), client.fixtures())

    @cached_property
    def players(self) -> dict[int, Element]:
        return {e.id: e for e in self.bootstrap.elements}

    @cached_property
    def teams(self) -> dict[int, Team]:
        return {t.id: t for t in self.bootstrap.teams}

    @cached_property
    def events(self) -> dict[int, Event]:
        return {e.id: e for e in self.bootstrap.events}

    @staticmethod
    def position(player: Element) -> str:
        return POSITIONS[player.element_type - 1]

    def upcoming_gameweeks(self, horizon: int) -> list[int]:
        """The next `horizon` gameweeks whose deadlines haven't passed, starting at the next one."""
        next_event = self.bootstrap.next_event()
        if next_event is None:
            return []
        return [gw for gw in range(next_event.id, next_event.id + horizon) if gw in self.events]

    @cached_property
    def fixtures_by_team(self) -> dict[int, dict[int, list[TeamFixture]]]:
        """team id -> gameweek -> that team's fixtures (none in a blank, two in a double)."""
        out: dict[int, dict[int, list[TeamFixture]]] = defaultdict(lambda: defaultdict(list))
        for f in self.fixtures:
            if f.event is None:
                continue
            out[f.team_h][f.event].append(TeamFixture(f.id, f.event, f.team_a, True, f.team_h_difficulty))
            out[f.team_a][f.event].append(TeamFixture(f.id, f.event, f.team_h, False, f.team_a_difficulty))
        return out

    def team_fixtures(self, team_id: int, gameweek: int) -> list[TeamFixture]:
        return self.fixtures_by_team.get(team_id, {}).get(gameweek, [])

    @cached_property
    def team_games_played(self) -> dict[int, int]:
        played: dict[int, int] = defaultdict(int)
        for f in self.fixtures:
            if f.finished:
                played[f.team_h] += 1
                played[f.team_a] += 1
        return played
