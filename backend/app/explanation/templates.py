"""Deterministic explanations written straight from the facts.

Always available (no model, no key, no cost) and the fallback whenever the local model is
missing, slow, or writes something that fails the checks. Every number comes from the facts.
"""


def _move_sentence(move: dict, window: str) -> str:
    sell, buy = move["sell"], move["buy"]
    sentence = (
        f"{sell['name']} → {buy['name']} (+{move['xp_gain']} xP over {window}): {buy['name']} "
        f"({buy['team']}, {buy['price']}) is projected {buy['xp_total']} xP to {sell['name']}'s {sell['xp_total']}"
    )
    extras = []
    if sell["status"] != "available":
        news = f" ({sell['news']})" if sell.get("news") else ""
        extras.append(f"{sell['name']} is {sell['status']}{news}")
    elif sell["hard_fixtures"] >= 2:
        extras.append(f"{sell['name']} faces {sell['hard_fixtures']} hard fixtures")
    if buy["easy_fixtures"] >= 2:
        extras.append(f"{buy['name']} has {buy['easy_fixtures']} easy fixtures")
    if extras:
        sentence += "; " + " and ".join(extras)
    return sentence + "."


def template_explanation(facts: dict) -> str:
    window = facts["planning_window"]
    sentences = []

    if facts["chip"]:
        sentences.append(f"Play your {facts['chip']} this gameweek.")

    if facts["moves"]:
        sentences += [_move_sentence(move, window) for move in facts["moves"]]
        hits = facts["hits"]
        cost = f" plus {hits} hit{'s' if hits > 1 else ''} (−{facts['hit_points']} points)" if hits else ""
        if facts["free_transfers"] is not None:
            sentences.append(
                f"That uses your free transfers{cost}, leaving {facts['bank_after']} in the bank."
            )
    elif "free_transfers_next_week" in facts:
        sentences.append(
            "No transfer gains enough to beat saving it: roll your free transfer and have "
            f"{facts['free_transfers_next_week']} next gameweek."
        )
    else:
        sentences.append("No transfer gains enough to be worth making this gameweek.")

    captain = facts["captain"]
    sentences.append(
        f"Captain {captain['name']} ({captain['fixtures']}, {captain['xp']} xP), "
        f"with {facts['vice_captain']} as vice-captain."
    )
    return " ".join(sentences)
