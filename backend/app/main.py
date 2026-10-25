"""HTTP API. Run locally with:  uvicorn app.main:app --reload"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import IngestRunRow
from app.fpl import FPLClient, FPLError, FPLNotFound
from app.manager.builder import NoSquadYet, build_manager_state
from app.manager.overrides import get_override, set_free_transfers
from app.manager.state import ManagerState
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


TeamId = Annotated[int, Path(ge=1, description="The number in your FPL points page URL")]
ClientDep = Annotated[FPLClient, Depends(get_client)]
RulesDep = Annotated[SeasonRules, Depends(get_rules)]
SessionDep = Annotated[Session, Depends(get_session)]


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
