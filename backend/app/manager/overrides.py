"""Read and write user overrides, keyed by FPL team ID (no accounts)."""

from sqlalchemy.orm import Session

from app.db.models import ManagerOverrideRow
from app.manager.builder import FreeTransferOverride


def get_override(session: Session, team_id: int) -> FreeTransferOverride | None:
    row = session.get(ManagerOverrideRow, team_id)
    if row is None:
        return None
    return FreeTransferOverride(planning_gameweek=row.planning_gameweek, free_transfers=row.free_transfers)


def set_free_transfers(session: Session, team_id: int, planning_gameweek: int, free_transfers: int | None) -> None:
    """Store an override for this gameweek, or clear it when free_transfers is None."""
    row = session.get(ManagerOverrideRow, team_id)
    if free_transfers is None:
        if row is not None:
            session.delete(row)
    elif row is None:
        session.add(ManagerOverrideRow(team_id=team_id, planning_gameweek=planning_gameweek, free_transfers=free_transfers))
    else:
        row.planning_gameweek = planning_gameweek
        row.free_transfers = free_transfers
    session.commit()
