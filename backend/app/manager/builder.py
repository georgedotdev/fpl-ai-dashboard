"""Build a ManagerState for one FPL team ID from public endpoints only (no login, no password)."""

from dataclasses import dataclass

from app.fpl import FPLClient
from app.fpl.models import Element
from app.manager.chips import chip_statuses
from app.manager.free_transfers import derive_free_transfers
from app.manager.selling_prices import latest_purchases, price_at_gameweek, selling_price
from app.manager.state import GameweekResult, ManagerState, Sourced, SquadPlayer
from app.rules import POSITIONS, SeasonRules
from app.rules.checks import check_against_bootstrap, chip_windows


class NoSquadYet(Exception):
    """The season hasn't started, or this manager has no squad past a deadline yet."""


@dataclass
class FreeTransferOverride:
    planning_gameweek: int
    free_transfers: int | None


def build_manager_state(
    client: FPLClient,
    team_id: int,
    rules: SeasonRules,
    override: FreeTransferOverride | None = None,
) -> ManagerState:
    bootstrap = client.bootstrap()
    entry = client.entry(team_id)
    history = client.entry_history(team_id)

    current = bootstrap.current_event()
    if current is None:
        raise NoSquadYet("The season hasn't started yet.")
    rows = sorted((r for r in history.current if r.event <= current.id), key=lambda r: r.event)
    if not rows:
        raise NoSquadYet(f"Team {team_id} has no squad yet; it will appear after its first deadline.")
    next_event = bootstrap.next_event()
    planning_gw = next_event.id if next_event else None

    warnings = [f"Rules check: {w}" for w in check_against_bootstrap(rules, bootstrap)]
    chip_by_gw = {c.event: c.name for c in history.chips}

    # The squad as it stands for the next deadline. After a Free Hit the squad (and bank)
    # revert, so show the squad from the gameweek before it.
    squad_gw = rows[-1].event
    picks = client.entry_picks(team_id, squad_gw)
    if picks.active_chip in rules.chips.reverting_chips and squad_gw - 1 >= entry.started_event:
        warnings.append(
            f"{rules.chips.labels.get(picks.active_chip, picks.active_chip)} active in GW{squad_gw}: "
            f"showing the GW{squad_gw - 1} squad you return to."
        )
        squad_gw -= 1
        picks = client.entry_picks(team_id, squad_gw)

    elements = {e.id: e for e in bootstrap.elements}
    teams = {t.id: t for t in bootstrap.teams}
    reverted_gws = {gw for gw, chip in chip_by_gw.items() if chip in rules.chips.reverting_chips}
    bought = latest_purchases(client.entry_transfers(team_id), ignore_gameweeks=reverted_gws)

    squad = []
    for pick in sorted(picks.picks, key=lambda p: p.position):
        el = elements[pick.element]
        purchase = _purchase_price(client, el, bought, entry.started_event)
        if purchase.value is None:
            sell = Sourced(value=el.now_cost, source="derived", note="Purchase price unknown; using current price.")
        else:
            sell = Sourced(
                value=selling_price(purchase.value, el.now_cost, rules.transfers.sell_on_fee),
                source="derived",
                note="Estimated: purchase price plus half of any rise, rounded down.",
            )
        squad.append(
            SquadPlayer(
                player_id=el.id,
                web_name=el.web_name,
                team_id=el.team,
                team_short_name=teams[el.team].short_name,
                position=POSITIONS[el.element_type - 1],
                slot=pick.position,
                is_captain=pick.is_captain,
                is_vice_captain=pick.is_vice_captain,
                bench_order=pick.position - rules.squad.starting_size
                if pick.position > rules.squad.starting_size
                else None,
                now_cost=el.now_cost,
                purchase_price=purchase,
                selling_price=sell,
                status=el.status,
                chance_of_playing_next_round=el.chance_of_playing_next_round,
                news=el.news,
            )
        )

    bank = picks.entry_history.bank
    free_transfers = _free_transfers(rows, history.chips, entry.started_event, rules, planning_gw, override, warnings)

    return ManagerState(
        team_id=team_id,
        manager_name=f"{entry.player_first_name} {entry.player_last_name}".strip(),
        team_name=entry.name,
        season=rules.season,
        current_gameweek=current.id,
        planning_gameweek=planning_gw,
        started_gameweek=entry.started_event,
        overall_rank=entry.summary_overall_rank,
        total_points=entry.summary_overall_points,
        squad_gameweek=squad_gw,
        squad_note=_squad_note(squad_gw, planning_gw),
        squad=squad,
        bank=Sourced(value=bank, source="api", note=f"As of the GW{squad_gw} deadline."),
        team_value=Sourced(
            value=bank + sum(p.now_cost for p in squad),
            source="api",
            note="Squad at today's prices plus bank.",
        ),
        sale_value=Sourced(
            value=bank + sum(p.selling_price.value for p in squad),
            source="derived",
            note="Bank plus the estimated selling price of every player: your real budget.",
        ),
        free_transfers=free_transfers,
        max_free_transfers=rules.transfers.max_banked,
        chips=chip_statuses(chip_windows(rules, bootstrap), history.chips, planning_gw or current.id + 1, rules),
        past_gameweeks=[
            GameweekResult(
                gameweek=r.event,
                points=r.points,
                total_points=r.total_points,
                overall_rank=r.overall_rank,
                bank=r.bank,
                team_value=r.value,
                transfers=r.event_transfers,
                transfer_cost=r.event_transfers_cost,
                points_on_bench=r.points_on_bench,
                chip=chip_by_gw.get(r.event),
            )
            for r in rows
        ],
        warnings=warnings,
    )


def _purchase_price(client: FPLClient, el: Element, bought: dict, started_event: int) -> Sourced[int | None]:
    if el.id in bought:
        t = bought[el.id]
        return Sourced(value=t.element_in_cost, source="api", note=f"From your transfer log (bought GW{t.event}).")
    if started_event == 1:
        # Prices don't move before the GW1 deadline, so the season's start price is what you paid.
        return Sourced(
            value=el.now_cost - el.cost_change_start,
            source="derived",
            note="In your squad since GW1: the player's start-of-season price.",
        )
    price = price_at_gameweek(client.element_summary(el.id), started_event)
    return Sourced(
        value=price,
        source="derived",
        note=f"In your squad since you joined in GW{started_event}: estimated from the player's price then.",
    )


def _free_transfers(rows, chips, started_event, rules, planning_gw, override, warnings) -> Sourced[int | None]:
    derived = derive_free_transfers(rows, chips, started_event, rules)
    warnings.extend(f"Free transfers: {c}" for c in derived.corrections)
    if override is not None:
        if override.planning_gameweek == planning_gw:
            return Sourced(
                value=override.free_transfers,
                source="user_override",
                note=f"Set by you for GW{planning_gw}. Our derived value was {derived.value}.",
            )
        warnings.append(
            f"Ignored your free-transfer override from GW{override.planning_gameweek}; "
            "it no longer applies. Showing the derived value."
        )
    return Sourced(value=derived.value, source="derived", note=derived.note)


def _squad_note(squad_gw: int, planning_gw: int | None) -> str:
    if planning_gw is None:
        return f"Your GW{squad_gw} squad. The season is over."
    return (
        f"Your squad at the GW{squad_gw} deadline. FPL doesn't publish transfers made since then "
        f"until the GW{planning_gw} deadline passes."
    )
