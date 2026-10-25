import httpx
import pytest
import respx

from app.fpl import FPLClient, FPLNotFound, FPLSchemaError, FPLUnavailable

BASE = "https://fpl.test/api/"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture(autouse=True)
def no_retry_backoff(monkeypatch):
    monkeypatch.setattr(FPLClient._fetch_json.retry, "sleep", lambda _seconds: None)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(clock: FakeClock) -> FPLClient:
    return FPLClient(
        http=httpx.Client(base_url=BASE),
        min_interval_s=0.5,
        clock=clock,
        sleep=clock.sleep,
    )


ENTRY = {
    "id": 42,
    "name": "Test FC",
    "player_first_name": "Ada",
    "player_last_name": "Lovelace",
    "started_event": 1,
    "current_event": 8,
    "summary_overall_points": 500,
    "summary_overall_rank": 12345,
    "some_field_we_ignore": True,
}


@respx.mock
def test_parses_and_ignores_unknown_fields(client):
    respx.get(BASE + "entry/42/").respond(json=ENTRY)
    entry = client.entry(42)
    assert entry.name == "Test FC"
    assert entry.started_event == 1


@respx.mock
def test_second_call_within_ttl_is_served_from_cache(client, clock):
    route = respx.get(BASE + "entry/42/").respond(json=ENTRY)
    client.entry(42)
    clock.now += 60  # inside the 120 s manager TTL
    client.entry(42)
    assert route.call_count == 1

    clock.now += 61  # now past it
    client.entry(42)
    assert route.call_count == 2


@respx.mock
def test_retries_on_503_then_succeeds(client):
    route = respx.get(BASE + "entry/42/").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=ENTRY)]
    )
    assert client.entry(42).id == 42
    assert route.call_count == 2


@respx.mock
def test_gives_up_after_three_attempts(client):
    route = respx.get(BASE + "entry/42/").respond(503)
    with pytest.raises(FPLUnavailable):
        client.entry(42)
    assert route.call_count == 3


@respx.mock
def test_404_is_not_found_and_not_retried(client):
    route = respx.get(BASE + "entry/999/").respond(404)
    with pytest.raises(FPLNotFound):
        client.entry(999)
    assert route.call_count == 1


@respx.mock
def test_html_holding_page_counts_as_unavailable(client):
    respx.get(BASE + "entry/42/").respond(200, text="<html>The game is being updated.</html>")
    with pytest.raises(FPLUnavailable):
        client.entry(42)


@respx.mock
def test_changed_shape_raises_schema_error(client):
    broken = {k: v for k, v in ENTRY.items() if k != "started_event"}
    respx.get(BASE + "entry/42/").respond(json=broken)
    with pytest.raises(FPLSchemaError, match="started_event"):
        client.entry(42)


@respx.mock
def test_requests_are_spaced_by_the_minimum_interval(client, clock):
    respx.get(BASE + "entry/1/").respond(json=ENTRY | {"id": 1})
    respx.get(BASE + "entry/2/").respond(json=ENTRY | {"id": 2})
    client.entry(1)
    clock.now += 0.1
    client.entry(2)
    assert clock.slept == [pytest.approx(0.4)]
