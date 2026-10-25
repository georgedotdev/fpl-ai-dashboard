"""Stage 2 baseline predictor: no machine learning, just a transparent formula.

    xP(player, gameweek) = scoring rate x availability x sum over fixtures of fixture factor

- scoring rate: points per team match, half recent form (FPL's `form`, last 30 days) and
  half season-long (total points / matches the team has played). Using team matches rather
  than appearances bakes in rotation risk.
- availability: see app/prediction/availability.py.
- fixture factor: a multiplier per FPL difficulty rating. A blank gameweek has no fixtures
  (0 points); a double has two.

FPL's own `ep_next` is just form x chance of playing: it ignores fixtures entirely and only
covers one gameweek, so it can't drive multi-week planning on its own.

The multipliers below are hand-set, not fitted. Stage 3 replaces this whole module with a
trained model behind the same interface.
"""

from datetime import UTC, date, datetime

from app.game import GameData
from app.prediction import XPMatrix
from app.prediction.availability import availability

NAME = "baseline-form-fixtures"
FORM_WEIGHT = 0.5
FIXTURE_FACTOR = {1: 1.20, 2: 1.10, 3: 1.00, 4: 0.90, 5: 0.80}


class BaselinePredictor:
    name = NAME

    def __init__(self, today: date | None = None) -> None:
        self._today = today

    def predict(self, game: GameData, gameweeks: list[int]) -> XPMatrix:
        today = self._today or datetime.now(UTC).date()
        deadlines = [game.events[gw].deadline_time for gw in gameweeks]
        expected: dict[int, list[float]] = {}
        available: dict[int, list[float]] = {}

        for player in game.bootstrap.elements:
            games = game.team_games_played.get(player.team, 0)
            season_rate = player.total_points / games if games else player.form
            rate = FORM_WEIGHT * player.form + (1 - FORM_WEIGHT) * season_rate
            avail = availability(player, deadlines, today)
            row = []
            for gw, a in zip(gameweeks, avail):
                fixtures = game.team_fixtures(player.team, gw)
                factor = sum(FIXTURE_FACTOR.get(f.difficulty, 1.0) for f in fixtures)
                row.append(round(max(rate, 0.0) * a * factor, 2))
            expected[player.id] = row
            available[player.id] = [round(a, 2) for a in avail]

        return XPMatrix(model=self.name, gameweeks=gameweeks, expected_points=expected, availability=available)
