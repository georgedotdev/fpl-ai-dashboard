"""Checks an explanation must pass before anyone sees it.

The explanation layer explains; it never decides or calculates. So an explanation may only
mention numbers that appear in its facts, and must name every player the plan moves.
These checks enforce that in code, whoever (or whatever) wrote the text.
"""

import json
import re

NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?")
TOLERANCE = 0.051  # allow "11.7" for 11.74 and the like


def numbers_in(text: str) -> list[float]:
    return [float(n) for n in NUMBER.findall(text)]


def check_explanation(text: str, facts: dict) -> list[str]:
    """Problems with the text; an empty list means it's fine to show."""
    problems = []
    if not text.strip():
        return ["The explanation is empty."]

    # ensure_ascii=False keeps "£6.6m" intact (escaped, "£6.6m" would read as 36.6)
    allowed = numbers_in(json.dumps(facts, ensure_ascii=False))
    invented = sorted({n for n in numbers_in(text) if not any(abs(n - a) <= TOLERANCE for a in allowed)})
    if invented:
        problems.append("Mentions numbers that aren't in the facts: " + ", ".join(f"{n:g}" for n in invented))

    for move in facts["moves"]:
        for side in ("sell", "buy"):
            name = move[side]["name"]
            if name.lower() not in text.lower():
                problems.append(f"Doesn't mention {name}, who the plan {'sells' if side == 'sell' else 'buys'}.")

    if len(text) > 300 + 250 * len(facts["moves"]):
        problems.append("Too long.")
    return problems
