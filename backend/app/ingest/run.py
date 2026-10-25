"""Scheduled ingestion: refresh game data from FPL and take today's price snapshot.

Run with:  python -m app.ingest.run

Safe to run as often as you like: every write is an upsert, and the price snapshot is keyed
by UK calendar day, so a late, repeated or missed GitHub Actions run does no harm.
"""

import sys
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import get_sessionmaker
from app.db.models import (
    Base,
    FixtureRow,
    GameweekRow,
    IngestRunRow,
    PlayerRow,
    PriceSnapshotRow,
    TeamRow,
)
from app.fpl import FPLClient
from app.fpl.models import Bootstrap, Fixture
from app.rules import POSITIONS, load_rules
from app.rules.checks import check_against_bootstrap
from app.settings import get_settings

UK = ZoneInfo("Europe/London")


def uk_date(now: datetime) -> date:
    """FPL prices change overnight UK time, so a snapshot belongs to the UK calendar day."""
    return now.astimezone(UK).date()


def upsert(session: Session, table: type[Base], rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(table).values(rows)
    keys = [c.name for c in table.__table__.primary_key.columns]
    updates = {c: stmt.excluded[c] for c in rows[0] if c not in keys}
    if "updated_at" in table.__table__.columns:
        updates["updated_at"] = func.now()
    session.execute(stmt.on_conflict_do_update(index_elements=keys, set_=updates))


def write_game_data(session: Session, bootstrap: Bootstrap, fixtures: list[Fixture], today: date) -> None:
    upsert(session, TeamRow, [
        {"id": t.id, "code": t.code, "name": t.name, "short_name": t.short_name}
        for t in bootstrap.teams
    ])
    upsert(session, GameweekRow, [
        e.model_dump(include={
            "id", "name", "deadline_time", "finished", "data_checked", "is_current",
            "is_next", "average_entry_score", "highest_score",
        })
        for e in bootstrap.events
    ])
    upsert(session, PlayerRow, [
        e.model_dump(include={
            "id", "code", "web_name", "first_name", "second_name", "now_cost",
            "cost_change_start", "status", "chance_of_playing_next_round", "news", "form",
            "points_per_game", "total_points", "selected_by_percent", "ep_next", "minutes",
        })
        | {"team_id": e.team, "position": POSITIONS[e.element_type - 1]}
        for e in bootstrap.elements
    ])
    upsert(session, FixtureRow, [
        f.model_dump(include={
            "id", "code", "event", "kickoff_time", "team_h", "team_a", "team_h_difficulty",
            "team_a_difficulty", "team_h_score", "team_a_score", "started", "finished",
        })
        for f in fixtures
    ])
    upsert(session, PriceSnapshotRow, [
        {
            "snapshot_date": today,
            "player_id": e.id,
            "now_cost": e.now_cost,
            "selected_by_percent": e.selected_by_percent,
            "transfers_in_event": e.transfers_in_event,
            "transfers_out_event": e.transfers_out_event,
        }
        for e in bootstrap.elements
    ])


def main() -> int:
    settings = get_settings()
    make_session = get_sessionmaker()
    client = FPLClient(settings.fpl_base_url, settings.fpl_timeout_s, settings.fpl_min_interval_s)

    with make_session() as session:
        run = IngestRunRow(started_at=datetime.now(UTC), status="running")
        session.add(run)
        session.commit()

    try:
        bootstrap = client.bootstrap()
        fixtures = client.fixtures()
        warnings = check_against_bootstrap(load_rules(settings.season), bootstrap)
        today = uk_date(datetime.now(UTC))
        with make_session() as session, session.begin():
            write_game_data(session, bootstrap, fixtures, today)
    except Exception as exc:
        run.finished_at = datetime.now(UTC)
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        with make_session() as session:
            session.merge(run)
            session.commit()
        print(f"Ingest failed: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()

    with make_session() as session:
        run.finished_at = datetime.now(UTC)
        run.status = "ok"
        run.players = len(bootstrap.elements)
        run.fixtures = len(fixtures)
        run.rule_warnings = warnings
        session.merge(run)
        session.commit()

    print(
        f"Ingest ok: {len(bootstrap.teams)} teams, {len(bootstrap.events)} gameweeks, "
        f"{len(bootstrap.elements)} players, {len(fixtures)} fixtures, "
        f"price snapshot for {today.isoformat()} (UK)."
    )
    for warning in warnings:
        print(f"RULES WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
