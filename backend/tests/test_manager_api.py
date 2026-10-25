"""End-to-end through the HTTP API with a fake FPL client and an in-memory database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_session
from app.db.models import Base
from app.fpl import FPLNotFound
from app.fpl.models import Fixture
from app.main import app, get_client
from tests import factories as f

SQUAD = list(range(1, 16))


class FakeFPL:
    """Serves hand-made responses. Team 42: joined GW1, now GW8, a few transfers."""

    def __init__(self, *, chips=None, picks_by_gw=None, rows=None, transfers=None, started=1):
        elements = f.standard_squad_elements()
        elements[6] |= {"now_cost": 57}  # player 7: bought at 5.4 in GW3, now 5.7 -> sells 5.5
        elements[0] |= {"now_cost": 46, "cost_change_start": -4}  # player 1: since GW1 at 5.0, now 4.6
        elements.append(f.element(16, team=6, position="MID", now_cost=80))
        self._bootstrap = f.bootstrap(elements=elements, current=8)
        self._rows = rows or [f.gw_row(1), f.gw_row(2), f.gw_row(3, transfers=1)] + [
            f.gw_row(gw) for gw in range(4, 9)
        ]
        self._chips = chips or {}
        self._picks = picks_by_gw or {}
        self._transfers = transfers if transfers is not None else [
            f.transfer(element_in=7, cost_in=54, element_out=16, event=3)
        ]
        self._started = started

    def bootstrap(self):
        return self._bootstrap

    def entry(self, team_id):
        if team_id != 42:
            raise FPLNotFound("nope")
        return f.entry(started_event=self._started)

    def entry_history(self, team_id):
        return f.history(self._rows, self._chips)

    def entry_picks(self, team_id, gw):
        return self._picks.get(gw) or f.picks(SQUAD, gw, captain=13, vice=9, bank=12)

    def entry_transfers(self, team_id):
        return self._transfers

    def element_summary(self, player_id):
        return f.element_summary({gw: 50 for gw in range(1, 9)})

    def fixtures(self):
        # Every gameweek: 1 v 2, 3 v 4, ... 19 v 20, at home with difficulty 2 (away 4).
        return [
            Fixture.model_validate({
                "id": gw * 100 + home, "code": gw * 100 + home, "event": gw, "kickoff_time": None,
                "team_h": home, "team_a": home + 1, "team_h_difficulty": 2, "team_a_difficulty": 4,
                "team_h_score": None, "team_a_score": None, "started": gw <= 8, "finished": gw <= 8,
            })
            for gw in range(1, 39)
            for home in range(1, 20, 2)
        ]


@pytest.fixture
def api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    make_session = sessionmaker(bind=engine, expire_on_commit=False)

    def session_override():
        with make_session() as session:
            yield session

    fake = {"fpl": FakeFPL()}
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_client] = lambda: fake["fpl"]
    yield TestClient(app), fake
    app.dependency_overrides.clear()


def test_manager_state(api):
    client, _ = api
    body = client.get("/manager/42").json()

    assert body["current_gameweek"] == 8 and body["planning_gameweek"] == 9
    assert len(body["squad"]) == 15
    assert [p["position"] for p in body["squad"]].count("DEF") == 5
    assert body["bank"] == {"value": 12, "source": "api", "note": "As of the GW8 deadline."}

    by_id = {p["player_id"]: p for p in body["squad"]}
    assert by_id[13]["is_captain"] and by_id[9]["is_vice_captain"]
    assert by_id[12]["bench_order"] == 1 and by_id[11]["bench_order"] is None
    # Bought in GW3 for 5.4, now 5.7: sells for 5.4 + floor(0.3 / 2) = 5.5
    assert by_id[7]["purchase_price"]["value"] == 54
    assert by_id[7]["selling_price"] == {
        "value": 55,
        "source": "derived",
        "note": "Estimated: purchase price plus half of any rise, rounded down.",
    }
    # Held since GW1 at 5.0, fell to 4.6: falls pass through in full
    assert by_id[1]["purchase_price"]["value"] == 50
    assert by_id[1]["selling_price"]["value"] == 46

    # 13 players at 5.0, one at 5.7, one at 4.6, plus 1.2 bank
    assert body["team_value"]["value"] == 13 * 50 + 57 + 46 + 12
    assert body["sale_value"]["value"] == 13 * 50 + 55 + 46 + 12

    # GW2 1 FT -> rolled to 2 for GW3 -> used 1 -> 2 for GW4 -> rolled 5 times -> capped at 5
    assert body["free_transfers"]["value"] == 5
    assert body["free_transfers"]["source"] == "derived"

    assert len(body["chips"]) == 8
    assert body["warnings"] == []


def test_unknown_team_is_404(api):
    client, _ = api
    response = client.get("/manager/7")
    assert response.status_code == 404
    assert response.json()["detail"] == "No FPL team with ID 7."


def test_free_hit_week_shows_the_squad_you_return_to(api):
    client, fake = api
    fh_squad = [1, 2, 3, 4, 5, 6, 16, 8, 9, 10, 11, 12, 13, 14, 15]
    fake["fpl"] = FakeFPL(
        chips={8: "freehit"},
        picks_by_gw={8: f.picks(fh_squad, 8, active_chip="freehit", bank=0), 7: f.picks(SQUAD, 7, bank=12)},
        transfers=[
            f.transfer(element_in=7, cost_in=54, element_out=16, event=3),
            f.transfer(element_in=16, cost_in=80, element_out=7, event=8),  # Free Hit: reverts
        ],
    )
    body = client.get("/manager/42").json()
    assert body["squad_gameweek"] == 7
    assert 16 not in {p["player_id"] for p in body["squad"]}
    assert body["bank"]["value"] == 12
    assert body["warnings"] == ["Free Hit active in GW8: showing the GW7 squad you return to."]
    by_id = {p["player_id"]: p for p in body["squad"]}
    assert by_id[7]["purchase_price"]["value"] == 54


def test_late_joiner_purchase_prices_come_from_price_history(api):
    client, fake = api
    fake["fpl"] = FakeFPL(started=5, rows=[f.gw_row(gw) for gw in range(5, 9)], transfers=[])
    body = client.get("/manager/42").json()
    p1 = next(p for p in body["squad"] if p["player_id"] == 1)
    assert p1["purchase_price"]["value"] == 50
    assert "joined in GW5" in p1["purchase_price"]["note"]
    assert body["free_transfers"]["value"] == 4  # GW6 1, GW7 2, GW8 3, GW9 4


def test_free_transfer_override_round_trip(api):
    client, _ = api
    body = client.patch("/manager/42/state", json={"free_transfers": 2}).json()
    assert body["free_transfers"]["value"] == 2
    assert body["free_transfers"]["source"] == "user_override"
    assert "derived value was 5" in body["free_transfers"]["note"]

    assert client.get("/manager/42").json()["free_transfers"]["source"] == "user_override"

    body = client.patch("/manager/42/state", json={"free_transfers": None}).json()
    assert body["free_transfers"] == client.get("/manager/42").json()["free_transfers"]
    assert body["free_transfers"]["source"] == "derived"


def test_override_out_of_range_is_rejected(api):
    client, _ = api
    assert client.patch("/manager/42/state", json={"free_transfers": 6}).status_code == 422


def test_override_from_an_earlier_gameweek_is_ignored(api):
    from app.manager import overrides

    client, _ = api
    session = next(app.dependency_overrides[get_session]())
    overrides.set_free_transfers(session, 42, planning_gameweek=8, free_transfers=1)
    body = client.get("/manager/42").json()
    assert body["free_transfers"]["source"] == "derived"
    assert any("override from GW8" in w for w in body["warnings"])
