"""The facts an explanation is allowed to use, taken from one recommended plan.

This dictionary is everything the explanation layer sees: the template writer reads it,
the local language model is given it as JSON, and the number check accepts only numbers
that appear in it. Values are pre-formatted the way a sentence would use them (£6.6m,
one decimal place for expected points), so nothing downstream needs to compute anything.
"""

from app.optimization.recommend import PlayerFacts, Recommendations, RecommendedPlan

STATUS_LABELS = {
    "a": "available",
    "d": "doubtful",
    "i": "injured",
    "s": "suspended",
    "u": "unavailable",
    "n": "not in the squad",
}
EASY, HARD = 2, 4  # FPL difficulty: 1-2 easy, 4-5 hard


def money(tenths: int) -> str:
    return f"£{tenths / 10:.1f}m"


def _player(p: PlayerFacts, price_key: str) -> dict:
    difficulties = [d for gw in p.fixture_difficulty for d in gw]
    out = {
        "name": p.web_name,
        "team": p.team_short_name,
        "position": p.position,
        price_key: money(p.price),
        "xp_total": round(p.xp_total, 1),
        "xp_next_gameweek": round(p.xp[0], 1),
        "status": STATUS_LABELS.get(p.status, p.status),
        "fixtures": ", ".join(f for gw in p.fixtures for f in gw) or "none",
        "easy_fixtures": sum(d <= EASY for d in difficulties),
        "hard_fixtures": sum(d >= HARD for d in difficulties),
    }
    if p.status != "a" and p.news:
        out["news"] = p.news
    return out


def build_facts(recs: Recommendations, plan: RecommendedPlan) -> dict:
    first = plan.gameweeks[0]
    gws = recs.gameweeks
    facts: dict = {
        "gameweek": first.gameweek,
        "planning_window": f"GW{gws[0]}-GW{gws[-1]}",
        "weeks_planned": len(gws),
        "free_transfers": first.free_transfers,
        "transfers": len(first.moves),
        "hits": first.hits,
        "hit_points": first.hit_points,
        "bank_after": money(first.bank),
        "chip": first.chip,
        "moves": [
            {
                "sell": _player(m.player_out, "selling_price"),
                "buy": _player(m.player_in, "price"),
                "xp_gain": round(m.xp_gain, 1),
            }
            for m in first.moves
        ],
        "captain": {
            "name": first.captain.web_name,
            "xp": round(first.captain.xp, 1),
            "fixtures": ", ".join(first.captain.fixtures) or "none",
        },
        "vice_captain": first.vice_captain.web_name,
        "plan_gain_vs_no_transfers": round(plan.gain_vs_no_transfers, 1),
    }
    if len(plan.gameweeks) > 1 and plan.gameweeks[1].free_transfers is not None:
        # The figure a "roll it" sentence needs, from the plan, so nothing has to add 1.
        facts["free_transfers_next_week"] = plan.gameweeks[1].free_transfers
    return facts
