"""Cross-check our season_rules config against what the live FPL API says.

FPL exposes some rule values in bootstrap-static (game_settings, element_types, chips).
Comparing them on every refresh turns a silent rule change into a loud warning.
"""

from app.fpl.models import Bootstrap
from app.rules import ChipWindowRule, SeasonRules


def chip_windows(rules: SeasonRules, bootstrap: Bootstrap | None) -> list[ChipWindowRule]:
    """Chip windows from the live API when it lists them, otherwise from config."""
    if bootstrap is None or not bootstrap.chips:
        return list(rules.chips.windows)
    windows = []
    for name in sorted({c.name for c in bootstrap.chips}):
        same_chip = sorted((c for c in bootstrap.chips if c.name == name), key=lambda c: c.start_event)
        for half, chip in enumerate(same_chip, start=1):
            windows.append(
                ChipWindowRule(name=name, half=half, start=chip.start_event, end=chip.stop_event)
            )
    return windows


def check_against_bootstrap(rules: SeasonRules, bootstrap: Bootstrap) -> list[str]:
    """Return a human-readable line for every rule where config and live API disagree."""
    problems: list[str] = []

    def compare(what: str, ours: object, theirs: object) -> None:
        if ours != theirs:
            problems.append(f"{what}: season_rules says {ours}, FPL API says {theirs}")

    gs = bootstrap.game_settings
    compare("squad size", rules.squad.size, gs.squad_squadsize)
    compare("starting XI size", rules.squad.starting_size, gs.squad_squadplay)
    compare("max players per club", rules.squad.max_per_club, gs.squad_team_limit)
    compare("budget (tenths of £m)", rules.squad.budget, gs.squad_total_spend)
    compare("sell-on fee", rules.transfers.sell_on_fee, gs.transfers_sell_on_fee)
    # FPL reports how many *extra* free transfers can be banked on top of the weekly one.
    compare("max banked free transfers", rules.transfers.max_banked, gs.max_extra_free_transfers + 1)

    for et in bootstrap.element_types:
        pos = et.singular_name_short
        compare(f"{pos} in squad", rules.squad.positions.get(pos), et.squad_select)
        compare(f"{pos} minimum in XI", rules.squad.starting_min.get(pos), et.squad_min_play)
        compare(f"{pos} maximum in XI", rules.squad.starting_max.get(pos), et.squad_max_play)

    if bootstrap.chips:
        key = lambda w: (w.name, w.half)  # noqa: E731
        ours = sorted(rules.chips.windows, key=key)
        theirs = sorted(chip_windows(rules, bootstrap), key=key)
        compare(
            "chip windows",
            [(w.name, w.half, w.start, w.end) for w in ours],
            [(w.name, w.half, w.start, w.end) for w in theirs],
        )
    else:
        problems.append("FPL API no longer lists chips; using chip windows from season_rules")

    return problems
