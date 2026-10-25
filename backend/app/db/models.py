"""Database tables. Money columns are in tenths of £1m, as FPL sends it."""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TeamRow(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    code: Mapped[int]
    name: Mapped[str] = mapped_column(String(64))
    short_name: Mapped[str] = mapped_column(String(8))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameweekRow(Base):
    __tablename__ = "gameweeks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(32))
    deadline_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished: Mapped[bool]
    data_checked: Mapped[bool]
    is_current: Mapped[bool]
    is_next: Mapped[bool]
    average_entry_score: Mapped[int | None]
    highest_score: Mapped[int | None]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlayerRow(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    code: Mapped[int]
    web_name: Mapped[str] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(64))
    second_name: Mapped[str] = mapped_column(String(64))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    position: Mapped[str] = mapped_column(String(3))
    now_cost: Mapped[int]
    cost_change_start: Mapped[int]
    status: Mapped[str] = mapped_column(String(1))
    chance_of_playing_next_round: Mapped[int | None]
    news: Mapped[str] = mapped_column(Text)
    form: Mapped[float]
    points_per_game: Mapped[float]
    total_points: Mapped[int]
    selected_by_percent: Mapped[float]
    ep_next: Mapped[float | None]
    minutes: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FixtureRow(Base):
    __tablename__ = "fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    code: Mapped[int]
    event: Mapped[int | None]  # None while postponed and not yet rescheduled
    kickoff_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    team_h: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    team_a: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    team_h_difficulty: Mapped[int]
    team_a_difficulty: Mapped[int]
    team_h_score: Mapped[int | None]
    team_a_score: Mapped[int | None]
    started: Mapped[bool | None]
    finished: Mapped[bool]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceSnapshotRow(Base):
    """One row per player per UK calendar day. FPL only gives today's price, so trends need these."""

    __tablename__ = "price_snapshots"

    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), primary_key=True)
    now_cost: Mapped[int]
    selected_by_percent: Mapped[float]
    transfers_in_event: Mapped[int]
    transfers_out_event: Mapped[int]
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestRunRow(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))  # running, ok, failed
    players: Mapped[int | None]
    fixtures: Mapped[int | None]
    rule_warnings: Mapped[list[str] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)


class ManagerOverrideRow(Base):
    """User corrections to derived values, keyed by FPL team ID (no user accounts; D-003).

    An override only applies to the gameweek it was made for: last week's free-transfer
    count is wrong by definition once the next deadline passes.
    """

    __tablename__ = "manager_overrides"

    team_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    planning_gameweek: Mapped[int]
    free_transfers: Mapped[int | None]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
