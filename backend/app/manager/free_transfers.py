"""Derive how many free transfers a manager has for the next deadline.

The exact number is only available behind FPL's login, so we replay the season from public
data: start with one after the first gameweek, add one per gameweek (capped), subtract
transfers made, and leave banked transfers alone in Wildcard/Free Hit weeks.

FPL's own hit charges are the ground truth we can check against: if FPL charged a different
number of hits than our count predicts, we re-sync to what FPL's charge implies and record
it. The user can still override the result.
"""

from dataclasses import dataclass, field

from app.fpl.models import ChipPlay, EntryGameweek
from app.rules import SeasonRules


@dataclass
class FreeTransferResult:
    value: int | None  # None: unlimited, the manager's first deadline hasn't passed
    note: str
    corrections: list[str] = field(default_factory=list)


def derive_free_transfers(
    rows: list[EntryGameweek],
    chips: list[ChipPlay],
    started_event: int,
    rules: SeasonRules,
) -> FreeTransferResult:
    """Free transfers available for the gameweek after the last row in `rows`."""
    tr = rules.transfers
    if not rows:
        return FreeTransferResult(None, "Unlimited transfers until your first deadline.")

    chip_by_gw = {c.event: c.name for c in chips}
    corrections: list[str] = []
    chip_weeks = 0
    ft: int | None = None

    for row in sorted(rows, key=lambda r: r.event):
        gw = row.event
        extra = tr.extra_free_transfers.get(gw + 1, 0)

        if ft is None or gw <= started_event:
            # The first gameweek's squad is picked freely; one free transfer after it.
            ft = min(tr.max_banked, tr.free_per_gameweek + extra)
            continue

        if chip_by_gw.get(gw) in rules.chips.free_transfer_chips:
            chip_weeks += 1
            remaining = ft if tr.chip_weeks.preserve_banked else 0
            gain = tr.free_per_gameweek if tr.chip_weeks.gains_free_transfer else 0
        else:
            hits_charged = row.event_transfers_cost // tr.hit_cost
            hits_expected = max(0, row.event_transfers - ft)
            if hits_charged != hits_expected:
                corrections.append(
                    f"GW{gw}: FPL charged {hits_charged} hit(s) where we expected {hits_expected}; re-synced"
                )
                # A charge pins down the true count exactly; no charge only gives a lower bound.
                ft = row.event_transfers - hits_charged if hits_charged else max(ft, row.event_transfers)
            remaining = max(0, ft - row.event_transfers)
            gain = tr.free_per_gameweek

        ft = min(tr.max_banked, remaining + gain + extra)

    note = f"Derived by replaying {len(rows)} gameweek(s) of your transfer history."
    if chip_weeks:
        note += (
            " Assumes banked transfers are kept through Wildcard/Free Hit weeks"
            + (" and the usual +1 still arrives." if tr.chip_weeks.gains_free_transfer else ".")
        )
    if corrections:
        note += " Re-synced against FPL's hit charges where our count drifted."
    return FreeTransferResult(ft, note, corrections)
