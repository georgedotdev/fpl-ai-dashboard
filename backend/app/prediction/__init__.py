"""The prediction brain: how many points will each player score in each upcoming gameweek?

Every predictor returns an XPMatrix (player x gameweek). That matrix is the only thing the
optimizer and dashboard see, so the Stage 2 baseline and the Stage 3 ML model are
interchangeable: pick one with the FPLAI_PREDICTOR setting.
"""

from typing import Protocol

from pydantic import BaseModel

from app.game import GameData


class XPMatrix(BaseModel):
    model: str  # which predictor produced this
    gameweeks: list[int]
    # player id -> expected points per gameweek, aligned with `gameweeks`
    expected_points: dict[int, list[float]]
    # player id -> estimated probability of being available per gameweek, aligned likewise
    availability: dict[int, list[float]]

    def xp(self, player_id: int, gameweek: int) -> float:
        return self.expected_points[player_id][self.gameweeks.index(gameweek)]

    def total(self, player_id: int, gameweeks: list[int] | None = None) -> float:
        row = self.expected_points[player_id]
        if gameweeks is None:
            return sum(row)
        return sum(row[self.gameweeks.index(gw)] for gw in gameweeks)


class Predictor(Protocol):
    name: str

    def predict(self, game: GameData, gameweeks: list[int]) -> XPMatrix: ...


def get_predictor(name: str) -> Predictor:
    from app.prediction.baseline import BaselinePredictor

    predictors: dict[str, Predictor] = {BaselinePredictor.name: BaselinePredictor()}
    if name not in predictors:
        raise ValueError(f"Unknown predictor {name!r}; choose from {sorted(predictors)}")
    return predictors[name]
