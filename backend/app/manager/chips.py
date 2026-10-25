"""Work out which chips a manager still has, from the chips they've played and the season's windows."""

from app.fpl.models import ChipPlay
from app.manager.state import ChipStatus
from app.rules import ChipWindowRule, SeasonRules

CHIP_ORDER = ["wildcard", "freehit", "bboost", "3xc"]


def chip_statuses(
    windows: list[ChipWindowRule],
    plays: list[ChipPlay],
    planning_gw: int,
    rules: SeasonRules,
) -> list[ChipStatus]:
    def order(w: ChipWindowRule) -> tuple[int, int]:
        rank = CHIP_ORDER.index(w.name) if w.name in CHIP_ORDER else len(CHIP_ORDER)
        return (w.half, rank)

    statuses = []
    for w in sorted(windows, key=order):
        base = dict(
            chip=w.name,
            label=rules.chips.labels.get(w.name, w.name),
            half=w.half,
            window_start=w.start,
            window_end=w.end,
        )
        played = next((p for p in plays if p.name == w.name and w.start <= p.event <= w.end), None)
        if played:
            statuses.append(ChipStatus(**base, state="used", played_gameweek=played.event))
            continue
        if w.end < planning_gw:
            statuses.append(ChipStatus(**base, state="expired"))
            continue

        usable_from = max(w.start, planning_gw)
        note = None
        if w.name in rules.chips.no_back_to_back:
            previous = next((p for p in plays if p.name == w.name and p.event == usable_from - 1), None)
            if previous:
                usable_from += 1
                note = f"Can't be played in GW{usable_from - 1}: you played one in GW{previous.event}."
        state = "available" if w.start <= planning_gw else "upcoming"
        statuses.append(ChipStatus(**base, state=state, usable_from_gameweek=usable_from, note=note))
    return statuses
