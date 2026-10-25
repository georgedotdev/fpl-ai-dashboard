"""HTTP API. Run locally with:  uvicorn app.main:app --reload"""

import hashlib
import time
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import IngestRunRow
from app.explanation import Explanation, explain
from app.explanation.local_model import OllamaExplainer
from app.fpl import FPLClient, FPLError, FPLNotFound
from app.game import GameData
from app.insights import PlayerSummary, TeamTicker, fixture_ticker, player_summaries
from app.manager.builder import NoSquadYet, build_manager_state
from app.manager.overrides import get_override, set_free_transfers
from app.manager.state import ManagerState
from app.optimization.recommend import Recommendations, recommend
from app.optimization.solver import Infeasible
from app.prediction import Predictor, XPMatrix, get_predictor
from app.rules import SeasonRules, load_rules
from app.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="AI FPL Assistant API",
    description="FPL manager state, predictions and recommendations. Money is in tenths of £1m.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "PATCH"],
    allow_headers=["Content-Type"],
)


@lru_cache
def get_client() -> FPLClient:
    return FPLClient(settings.fpl_base_url, settings.fpl_timeout_s, settings.fpl_min_interval_s)


def get_rules() -> SeasonRules:
    return load_rules(settings.season)


def get_prediction_model() -> Predictor:
    return get_predictor(settings.predictor)


def get_game(client: Annotated[FPLClient, Depends(get_client)]) -> GameData:
    try:
        return GameData.load(client)
    except FPLError as exc:
        raise HTTPException(502, f"Couldn't get data from FPL right now: {exc}")


TeamId = Annotated[int, Path(ge=1, description="The number in your FPL points page URL")]
Horizon = Annotated[
    int,
    Query(ge=1, le=settings.max_horizon, description="How many gameweeks ahead to look, from the next deadline"),
]
ClientDep = Annotated[FPLClient, Depends(get_client)]
RulesDep = Annotated[SeasonRules, Depends(get_rules)]
SessionDep = Annotated[Session, Depends(get_session)]
GameDep = Annotated[GameData, Depends(get_game)]
PredictorDep = Annotated[Predictor, Depends(get_prediction_model)]


@app.get("/health")
def health(session: SessionDep) -> dict:
    try:
        session.execute(text("select 1"))
        last = session.scalars(
            select(IngestRunRow).where(IngestRunRow.status == "ok").order_by(IngestRunRow.id.desc()).limit(1)
        ).first()
    except Exception as exc:  # report, don't crash: health must always answer
        return {"status": "degraded", "database": f"error: {type(exc).__name__}"}
    return {
        "status": "ok",
        "database": "ok",
        "last_ingest": last.finished_at if last else None,
        "rule_warnings": last.rule_warnings if last else None,
    }


def _state(client: FPLClient, rules: SeasonRules, session: Session, team_id: int) -> ManagerState:
    try:
        return build_manager_state(client, team_id, rules, get_override(session, team_id))
    except FPLNotFound:
        raise HTTPException(404, f"No FPL team with ID {team_id}.")
    except NoSquadYet as exc:
        raise HTTPException(409, str(exc))
    except FPLError as exc:
        raise HTTPException(502, f"Couldn't get data from FPL right now: {exc}")


@app.get("/manager/{team_id}")
def get_manager(team_id: TeamId, client: ClientDep, rules: RulesDep, session: SessionDep) -> ManagerState:
    return _state(client, rules, session, team_id)


class StateOverrides(BaseModel):
    free_transfers: int | None = Field(
        description="Your real free-transfer count for the next deadline, or null to go back to ours.",
    )


@app.patch("/manager/{team_id}/state")
def patch_manager_state(
    team_id: TeamId, body: StateOverrides, client: ClientDep, rules: RulesDep, session: SessionDep
) -> ManagerState:
    state = _state(client, rules, session, team_id)
    if state.planning_gameweek is None:
        raise HTTPException(409, "The season is over; there's no next deadline to set transfers for.")
    if body.free_transfers is not None and not 0 <= body.free_transfers <= rules.transfers.max_banked:
        raise HTTPException(422, f"Free transfers must be between 0 and {rules.transfers.max_banked}.")
    set_free_transfers(session, team_id, state.planning_gameweek, body.free_transfers)
    return _state(client, rules, session, team_id)


# --- dashboard views -----------------------------------------------------------------


class PlayersResponse(BaseModel):
    model: str = Field(description="The predictor behind the xp_ columns")
    gameweeks: list[int]
    players: list[PlayerSummary]


def _predict(game: GameData, predictor: Predictor, horizon: int) -> XPMatrix:
    gameweeks = game.upcoming_gameweeks(horizon)
    if not gameweeks:
        raise HTTPException(409, "The season is over; there are no gameweeks left to predict.")
    return predictor.predict(game, gameweeks)


def _filter(players: list[PlayerSummary], position: str | None, max_price: int | None) -> list[PlayerSummary]:
    return [
        p for p in players
        if (position is None or p.position == position) and (max_price is None or p.now_cost <= max_price)
    ]


Position = Annotated[str | None, Query(pattern="^(GKP|DEF|MID|FWD)$")]
MaxPrice = Annotated[int | None, Query(ge=0, description="Tenths of £1m, e.g. 65 for £6.5m")]
SORTABLE = ("xp_horizon", "xp_next", "xp_per_million", "now_cost", "form", "selected_by_percent",
            "cost_change_event", "net_transfers_event", "total_points")


@app.get("/players")
def list_players(
    game: GameDep,
    predictor: PredictorDep,
    horizon: Horizon = settings.default_horizon,
    position: Position = None,
    max_price: MaxPrice = None,
    sort: Annotated[str, Query(pattern="^(" + "|".join(SORTABLE) + ")$")] = "xp_horizon",
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> PlayersResponse:
    xp = _predict(game, predictor, horizon)
    players = _filter(player_summaries(game, xp), position, max_price)
    players.sort(key=lambda p: getattr(p, sort), reverse=True)
    return PlayersResponse(model=xp.model, gameweeks=xp.gameweeks, players=players[:limit])


@app.get("/captaincy")
def captaincy(game: GameDep, predictor: PredictorDep, limit: Annotated[int, Query(ge=1, le=50)] = 10) -> PlayersResponse:
    """Best captain picks for the next gameweek: highest expected points, before doubling."""
    xp = _predict(game, predictor, 1)
    players = sorted(player_summaries(game, xp), key=lambda p: p.xp_next, reverse=True)
    return PlayersResponse(model=xp.model, gameweeks=xp.gameweeks, players=players[:limit])


@app.get("/picks/best-by-fixtures")
def best_by_fixtures(
    game: GameDep,
    predictor: PredictorDep,
    horizon: Horizon = settings.default_horizon,
    position: Position = None,
    max_price: MaxPrice = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> PlayersResponse:
    """Best players over the next few gameweeks, by expected points (optionally per position / price cap)."""
    xp = _predict(game, predictor, horizon)
    players = [p for p in _filter(player_summaries(game, xp), position, max_price) if p.status not in ("u", "n")]
    players.sort(key=lambda p: p.xp_horizon, reverse=True)
    return PlayersResponse(model=xp.model, gameweeks=xp.gameweeks, players=players[:limit])


class FixturesResponse(BaseModel):
    gameweeks: list[int]
    teams: list[TeamTicker]


@app.get("/fdr")
def fdr(game: GameDep, horizon: Horizon = settings.default_horizon) -> FixturesResponse:
    """Fixture ticker with FPL difficulty ratings, teams with the easiest run first."""
    gameweeks = game.upcoming_gameweeks(horizon)
    return FixturesResponse(gameweeks=gameweeks, teams=fixture_ticker(game, gameweeks))


# --- recommendations ---------------------------------------------------------------

# Solving takes a few seconds, so identical requests (same squad, bank, free transfers,
# predictions and horizon) reuse the last answer for a while.
RECOMMENDATION_TTL_S = 600
_recommendation_cache: dict[str, tuple[float, Recommendations]] = {}


@app.get("/recommendations/{team_id}")
def get_recommendations(
    team_id: TeamId,
    client: ClientDep,
    rules: RulesDep,
    session: SessionDep,
    game: GameDep,
    predictor: PredictorDep,
    horizon: Horizon = settings.default_horizon,
) -> Recommendations:
    return _recommendations(team_id, client, rules, session, game, predictor, horizon)


def _recommendations(team_id, client, rules, session, game, predictor, horizon) -> Recommendations:
    state = _state(client, rules, session, team_id)
    xp = _predict(game, predictor, horizon)
    key = hashlib.sha256((state.model_dump_json() + xp.model_dump_json()).encode()).hexdigest()
    hit = _recommendation_cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    try:
        result = recommend(state, game, xp, rules)
    except Infeasible as exc:
        raise HTTPException(422, f"Couldn't find a valid plan for this squad: {exc}")
    if len(_recommendation_cache) > 256:
        _recommendation_cache.clear()
    _recommendation_cache[key] = (time.monotonic() + RECOMMENDATION_TTL_S, result)
    return result


# --- explanations ----------------------------------------------------------------------


@lru_cache
def get_local_explainer() -> OllamaExplainer | None:
    """The local language model, if one is configured (FPLAI_LOCAL_MODEL); else templates only."""
    if not settings.local_model:
        return None
    return OllamaExplainer(settings.ollama_url, settings.local_model, settings.local_model_timeout_s)


_explanation_cache: dict[str, Explanation] = {}


@app.get("/recommendations/{team_id}/explanation")
def get_explanation(
    team_id: TeamId,
    client: ClientDep,
    rules: RulesDep,
    session: SessionDep,
    game: GameDep,
    predictor: PredictorDep,
    local: Annotated[OllamaExplainer | None, Depends(get_local_explainer)],
    horizon: Horizon = settings.default_horizon,
    plan: Annotated[int, Query(ge=1, description="Which plan to explain, by rank")] = 1,
) -> Explanation:
    """Plain-English reasons for a recommended plan, written only from that plan's facts."""
    recs = _recommendations(team_id, client, rules, session, game, predictor, horizon)
    chosen = next((p for p in recs.plans if p.rank == plan), None)
    if chosen is None:
        raise HTTPException(404, f"There is no plan {plan}; this team has {len(recs.plans)}.")
    key = hashlib.sha256((chosen.model_dump_json() + str(local and local.model)).encode()).hexdigest()
    if key in _explanation_cache:
        return _explanation_cache[key]
    result = explain(recs, chosen, local)
    if result.note is None:  # don't keep a fallback: the local model may be back next time
        if len(_explanation_cache) > 512:
            _explanation_cache.clear()
        _explanation_cache[key] = result
    return result
