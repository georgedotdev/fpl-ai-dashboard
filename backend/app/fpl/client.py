"""The one and only FPL API client.

Responsibilities, all in one place:
- caching (per-endpoint TTL, in memory),
- rate limiting (a minimum gap between requests, across threads),
- retries with backoff on network errors, 5xx and 429,
- response validation against the models in app.fpl.models.

The FPL API is unofficial and can change without notice; anything that goes wrong talking
to it surfaces as an FPLError subclass raised from here.
"""

import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx
from pydantic import TypeAdapter, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.fpl.models import (
    Bootstrap,
    ElementSummary,
    Entry,
    EntryHistory,
    EntryPicks,
    Fixture,
    Transfer,
)

T = TypeVar("T")

# How long each kind of response is reused before asking FPL again, in seconds.
TTL_GAME_DATA = 300  # bootstrap-static, fixtures
TTL_MANAGER = 120  # entry/{id}/...
TTL_PLAYER_HISTORY = 3600  # element-summary/{id}/


class FPLError(Exception):
    """Base class for every failure talking to the FPL API."""


class FPLNotFound(FPLError):
    """FPL returned 404, e.g. a team ID that doesn't exist."""


class FPLUnavailable(FPLError):
    """FPL is unreachable or erroring (it returns 503 while gameweeks are being updated)."""


class FPLSchemaError(FPLError):
    """FPL answered, but not in the shape we expect: the API has probably changed."""


class FPLClient:
    def __init__(
        self,
        base_url: str = "https://fantasy.premierleague.com/api/",
        timeout_s: float = 15.0,
        min_interval_s: float = 0.2,
        http: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = http or httpx.Client(
            base_url=base_url,
            timeout=timeout_s,
            headers={"User-Agent": "fpl-ai-assistant (portfolio project)"},
        )
        self._min_interval_s = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._last_request_at: float | None = None

    # --- public endpoints ----------------------------------------------------------

    def bootstrap(self) -> Bootstrap:
        return self._get("bootstrap-static/", Bootstrap, TTL_GAME_DATA)

    def fixtures(self) -> list[Fixture]:
        return self._get("fixtures/", list[Fixture], TTL_GAME_DATA)

    def entry(self, team_id: int) -> Entry:
        return self._get(f"entry/{team_id}/", Entry, TTL_MANAGER)

    def entry_history(self, team_id: int) -> EntryHistory:
        return self._get(f"entry/{team_id}/history/", EntryHistory, TTL_MANAGER)

    def entry_picks(self, team_id: int, gameweek: int) -> EntryPicks:
        return self._get(f"entry/{team_id}/event/{gameweek}/picks/", EntryPicks, TTL_MANAGER)

    def entry_transfers(self, team_id: int) -> list[Transfer]:
        return self._get(f"entry/{team_id}/transfers/", list[Transfer], TTL_MANAGER)

    def element_summary(self, player_id: int) -> ElementSummary:
        return self._get(f"element-summary/{player_id}/", ElementSummary, TTL_PLAYER_HISTORY)

    def close(self) -> None:
        self._http.close()

    # --- internals ------------------------------------------------------------------

    def _get(self, path: str, model: type[T] | Any, ttl_s: float) -> T:
        with self._cache_lock:
            hit = self._cache.get(path)
            if hit is not None and hit[0] > self._clock():
                return hit[1]

        raw = self._fetch_json(path)
        try:
            parsed = TypeAdapter(model).validate_python(raw)
        except ValidationError as exc:
            raise FPLSchemaError(
                f"FPL response for {path!r} no longer matches the expected shape: {exc}"
            ) from exc

        with self._cache_lock:
            self._cache[path] = (self._clock() + ttl_s, parsed)
        return parsed

    @retry(
        retry=retry_if_exception_type(FPLUnavailable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    def _fetch_json(self, path: str) -> Any:
        self._wait_for_rate_limit()
        try:
            response = self._http.get(path)
        except httpx.TransportError as exc:
            raise FPLUnavailable(f"Could not reach FPL for {path!r}: {exc}") from exc

        if response.status_code == 404:
            raise FPLNotFound(f"FPL has nothing at {path!r}")
        if response.status_code == 429 or response.status_code >= 500:
            raise FPLUnavailable(f"FPL returned {response.status_code} for {path!r}")
        if response.status_code != 200:
            raise FPLError(f"FPL returned {response.status_code} for {path!r}")
        try:
            return response.json()
        except ValueError as exc:
            # During updates FPL sometimes serves an HTML holding page with status 200.
            raise FPLUnavailable(f"FPL returned non-JSON for {path!r}") from exc

    def _wait_for_rate_limit(self) -> None:
        with self._rate_lock:
            now = self._clock()
            if self._last_request_at is not None:
                gap = now - self._last_request_at
                if gap < self._min_interval_s:
                    self._sleep(self._min_interval_s - gap)
            self._last_request_at = self._clock()
