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


def test_explanation_endpoint_uses_templates_without_a_local_model(api):  # noqa: F811
    from app.main import app, get_local_explainer

    client, _ = api
    app.dependency_overrides[get_local_explainer] = lambda: None
    body = client.get("/recommendations/42/explanation?horizon=2").json()
    assert body["plan_rank"] == 1 and body["source"] == "template" and body["model"] is None
    assert "Captain" in body["text"]
    assert body["facts"]["planning_window"] == "GW9-GW10"
    assert client.get("/recommendations/42/explanation?horizon=2&plan=9").status_code == 404


MANUAL = {"player_ids": list(range(1, 16)), "bank": 12, "free_transfers": 1, "chips_available": ["wildcard-1"]}


def test_manual_squad_state_and_recommendations(api):  # noqa: F811
    client, _ = api
    state = client.post("/manual/state", json=MANUAL).json()
    assert state["team_name"] == "Your squad (entered by hand)" and len(state["squad"]) == 15
    recs = client.post("/manual/recommendations?horizon=2", json=MANUAL).json()
    assert recs["gameweeks"] == [9, 10] and recs["plans"][0]["rank"] == 1
    assert recs["free_transfers"] == {"value": 1, "source": "user_override", "note": "Entered by you."}


def test_manual_explanation(api):  # noqa: F811
    from app.main import app, get_local_explainer

    client, _ = api
    app.dependency_overrides[get_local_explainer] = lambda: None
    body = client.post("/manual/recommendations/explanation?horizon=2", json=MANUAL).json()
    assert body["source"] == "template" and "Captain" in body["text"]


def test_manual_squad_problems_come_back_as_one_readable_422(api):  # noqa: F811
    client, _ = api
    response = client.post("/manual/state", json=MANUAL | {"player_ids": list(range(1, 15))})
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Pick exactly 15 players (you have 14).")


def test_rules_endpoint_lists_shape_and_open_chips(api):  # noqa: F811
    client, _ = api
    body = client.get("/rules").json()
    assert body["positions"] == {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3} and body["max_per_club"] == 3
    open_now = {c["key"] for c in body["chips"] if c["open_now"]}
    assert open_now == {"wildcard-1", "freehit-1", "bboost-1", "3xc-1"}


def test_best_xi_is_a_legal_squad_within_budget(api):  # noqa: F811
    client, _ = api
    body = client.get("/best-xi").json()
    assert body["gameweek"] == 9 and len(body["lineup"]) == 11 and len(body["bench"]) == 4
    squad = body["lineup"] + body["bench"]
    assert [p["position"] for p in squad].count("GKP") == 2
    assert body["cost"] <= body["budget"] == 1000
    clubs = [p["team_short_name"] for p in squad]
    assert max(clubs.count(c) for c in clubs) <= 3
    assert body["captain"]["player_id"] in {p["player_id"] for p in body["lineup"]}
    assert body["bench"][0]["position"] == "GKP"
    assert {"price", "status", "news", "fixtures"} <= set(body["lineup"][0])


def test_recommendations_include_the_current_squad_in_slot_order(api):  # noqa: F811
    client, _ = api
    body = client.get("/recommendations/42?horizon=2").json()
    assert [p["player_id"] for p in body["current"]] == list(range(1, 16))
    assert body["current_captain"] == 13 and body["current_vice_captain"] == 9
    assert all("xp" in p and "fixtures" in p for p in body["current"])


def test_heavy_endpoints_are_rate_limited_per_visitor(api, monkeypatch):  # noqa: F811
    from app import main

    client, _ = api
    monkeypatch.setattr(main.settings, "rate_limit_per_minute", 2)
    main._recent_requests.clear()
    assert client.get("/best-xi").status_code == 200
    assert client.get("/best-xi").status_code == 200
    limited = client.get("/best-xi")
    assert limited.status_code == 429 and limited.headers["Retry-After"] == "60"
    assert client.get("/players?limit=1").status_code == 200  # light endpoints aren't limited
    main._recent_requests.clear()
