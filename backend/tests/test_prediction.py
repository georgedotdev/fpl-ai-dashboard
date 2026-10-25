from datetime import UTC, date, datetime

import pytest

from app.fpl.models import Element, Fixture
from app.game import GameData
from app.prediction import get_predictor
from app.prediction.availability import availability, return_date
from app.prediction.baseline import BaselinePredictor
from tests import factories as f

TODAY = date(2026, 10, 25)
# GW9-GW11 deadlines, one week apart (Saturdays)
DEADLINES = [datetime(2026, 10, 31, 11, tzinfo=UTC), datetime(2026, 11, 7, 11, tzinfo=UTC), datetime(2026, 11, 14, 11, tzinfo=UTC)]


def player(**kw) -> Element:
    return Element.model_validate(f.element(1, **kw))


@pytest.mark.parametrize(
    ("news", "expected"),
    [
        ("Hamstring injury - Expected back 8 Nov", date(2026, 11, 8)),
        ("Suspended until 1 Nov", date(2026, 11, 1)),
        ("Knee injury - Expected back 3 Jan", date(2027, 1, 3)),  # next calendar year
        ("Thigh injury - Unknown return date", None),
        ("75% chance of playing", None),
    ],
)
def test_return_date(news, expected):
    assert return_date(news, TODAY) == expected


def test_available_player_is_fully_available():
    assert availability(player(), DEADLINES, TODAY) == [1.0, 1.0, 1.0]


def test_doubtful_player_uses_fpl_chance_next_round_then_recovers():
    p = player(status="d", chance_of_playing_next_round=75, news="Knock - 75% chance of playing")
    assert availability(p, DEADLINES, TODAY) == [0.75, 1.0, 1.0]


def test_injured_with_return_date_comes_back_that_gameweek():
    # Back 8 Nov: misses GW9 (deadline 31 Oct), plays GW10 (deadline 7 Nov + 2 days grace)
    p = player(status="i", chance_of_playing_next_round=0, news="Hamstring injury - Expected back 8 Nov")
    assert availability(p, DEADLINES, TODAY) == [0.0, 1.0, 1.0]


def test_injured_with_unknown_return_stays_out():
    p = player(status="i", chance_of_playing_next_round=0, news="Thigh injury - Unknown return date")
    assert availability(p, DEADLINES, TODAY) == [0.0, 0.0, 0.0]


def test_departed_player_without_a_chance_figure_is_out():
    p = player(status="u", chance_of_playing_next_round=None, news="Has joined Juventus on loan")
    assert availability(p, DEADLINES, TODAY) == [0.0, 0.0, 0.0]


def fixture(id, event, home, away, dh=3, da=3, finished=False) -> Fixture:
    return Fixture.model_validate({
        "id": id, "code": id, "event": event, "kickoff_time": None, "team_h": home, "team_a": away,
        "team_h_difficulty": dh, "team_a_difficulty": da, "team_h_score": None, "team_a_score": None,
        "started": finished, "finished": finished,
    })


def test_baseline_formula_by_hand():
    # Team 1 has played 8 games. Player 1: 48 points (6.0 per team game), form 4.0
    # -> rate 0.5*4.0 + 0.5*6.0 = 5.0
    # GW9: one fixture, difficulty 2 (x1.1) -> 5.5
    # GW10: blank -> 0
    # GW11: double, difficulties 3 and 5 (x1.0 + x0.8) -> 9.0
    players = [f.element(1, team=1, form="4.0", total_points=48)]
    fixtures = [fixture(100 + i, i, 1, 2, finished=True) for i in range(1, 9)]
    fixtures += [fixture(200, 9, 1, 3, dh=2), fixture(201, 11, 4, 1, da=3), fixture(202, 11, 1, 5, dh=5)]
    game = GameData(f.bootstrap(elements=players, current=8), fixtures)

    xp = BaselinePredictor(today=TODAY).predict(game, [9, 10, 11])
    assert xp.expected_points[1] == [5.5, 0.0, 9.0]
    assert xp.total(1) == pytest.approx(14.5)
    assert xp.availability[1] == [1.0, 1.0, 1.0]


def test_injured_player_gets_low_expected_points_not_a_special_rule():
    players = [f.element(1, team=1, form="6.0", total_points=48, status="i", chance_of_playing_next_round=0,
                         news="Hamstring injury - Expected back 20 Oct")]
    # Factory deadlines: GW9 16 Oct, GW10 23 Oct, GW11 30 Oct. Out for GW9, back for GW10.
    fixtures = [fixture(100 + i, i, 1, 2, finished=True) for i in range(1, 9)]
    fixtures += [fixture(200 + gw, gw, 1, 3) for gw in (9, 10, 11)]
    game = GameData(f.bootstrap(elements=players, current=8), fixtures)
    assert BaselinePredictor(today=TODAY).predict(game, [9, 10, 11]).expected_points[1] == [0.0, 6.0, 6.0]


def test_predictors_are_looked_up_by_name():
    assert get_predictor("baseline-form-fixtures").name == "baseline-form-fixtures"
    with pytest.raises(ValueError):
        get_predictor("nope")
