"""Dashboard and recommendation endpoints, end to end with the fake FPL from test_manager_api."""

import pytest

from tests.test_manager_api import api  # noqa: F401  (pytest fixture)


def test_players_have_expected_points_over_the_horizon(api):  # noqa: F811
    client, _ = api
    body = client.get("/players?horizon=3").json()
    assert body["model"] == "baseline-form-fixtures"
    assert body["gameweeks"] == [9, 10, 11]
    players = body["players"]
    assert len(players) == 16
    assert all(len(p["upcoming"]) == 3 for p in players)
    totals = [p["xp_horizon"] for p in players]
    assert totals == sorted(totals, reverse=True)


def test_players_filter_by_position_and_price(api):  # noqa: F811
    client, _ = api
    players = client.get("/players?position=MID&max_price=60").json()["players"]
    assert players and all(p["position"] == "MID" and p["now_cost"] <= 60 for p in players)


def test_fdr_lists_every_team_with_the_easiest_first(api):  # noqa: F811
    client, _ = api
    body = client.get("/fdr?horizon=2").json()
    assert body["gameweeks"] == [9, 10]
    teams = body["teams"]
    assert len(teams) == 20
    # Odd-numbered teams play at home (difficulty 2) every week, so they come first.
    assert teams[0]["average_difficulty"] == 2.0 and teams[-1]["average_difficulty"] == 4.0
    assert teams[0]["gameweeks"][0][0]["home"] is True


def test_captaincy_is_next_gameweek_only(api):  # noqa: F811
    client, _ = api
    body = client.get("/captaincy?limit=3").json()
    assert body["gameweeks"] == [9] and len(body["players"]) == 3


@pytest.mark.parametrize("horizon", [1, 3])
def test_recommendations_are_consistent(api, horizon):  # noqa: F811
    client, _ = api
    body = client.get(f"/recommendations/42?horizon={horizon}").json()
    assert body["gameweeks"] == list(range(9, 9 + horizon))
    assert 1 <= len(body["plans"]) <= 3
    best = body["plans"][0]
    assert best["rank"] == 1
    assert best["gain_vs_no_transfers"] == pytest.approx(best["expected_points"] - body["no_transfers_expected_points"], abs=0.01)
    for gw in best["gameweeks"]:
        assert len(gw["lineup"]) == 11 and len(gw["bench"]) == 4
        assert gw["bench"][0]["position"] == "GKP"
        assert gw["captain"]["player_id"] != gw["vice_captain"]["player_id"]
        assert gw["bank"] >= 0
        for move in gw["moves"]:
            assert move["player_out"]["position"] == move["player_in"]["position"]
    assert body["free_transfers"]["source"] == "derived"


def test_recommendations_reject_a_silly_horizon(api):  # noqa: F811
    client, _ = api
    assert client.get("/recommendations/42?horizon=20").status_code == 422


def test_recommendations_include_advice_for_every_chip_held(api):  # noqa: F811
    client, _ = api
    body = client.get("/recommendations/42?horizon=3").json()
    chips = {(c["chip"], c["half"]): c for c in body["chips"]}
    assert len(chips) == 8  # nothing played yet in the fake season
    # First-half chips are playable but have 10+ weeks left, so on these flat fixtures:
    first_bb = chips[("bboost", 1)]
    assert first_bb["play_in_gameweek"] is None and first_bb["advice"].startswith("Save it")
    assert first_bb["opportunity_cost"] == 12.0  # Bench Boost par, full while 4+ weeks remain
    # Second-half chips open in GW20, outside GW9-11
    assert chips[("wildcard", 2)]["advice"].startswith("Not playable")
    assert all(gw["chip"] is None for gw in body["plans"][0]["gameweeks"])
