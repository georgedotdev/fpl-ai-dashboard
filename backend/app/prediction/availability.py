"""How likely is a player to be available in each upcoming gameweek?

FPL gives a chance of playing for the *next* round only, plus free-text news that often
carries a return date ("Expected back 1 Nov", "Suspended until 8 Nov"). We use FPL's chance
for the next round, and the return date for the rounds after. Injuries are weighed, not
special-cased: availability scales expected points, and the optimizer decides whether a
transfer is worth it.
"""

import re
from datetime import date, datetime, timedelta

from app.fpl.models import Element

RETURN_DATE = re.compile(r"(?:Expected back|Suspended until)\s+(\d{1,2})\s+([A-Z][a-z]{2})")
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1
)}

# Statuses meaning "won't play": injured, suspended, unavailable (left the club), not in squad.
OUT = {"i", "s", "u", "n"}

# A player back within this long after a deadline still counts for that gameweek: most of
# a gameweek's matches are played in the few days after its deadline.
GAMEWEEK_GRACE = timedelta(days=2)


def return_date(news: str, today: date) -> date | None:
    """Parse a return date from FPL news. FPL omits the year: pick the one nearest today."""
    match = RETURN_DATE.search(news)
    if not match or match.group(2) not in MONTHS:
        return None
    day, month = int(match.group(1)), MONTHS[match.group(2)]
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    return min(candidates, key=lambda d: abs(d - today)) if candidates else None


def availability(player: Element, deadlines: list[datetime], today: date) -> list[float]:
    """Probability of being available for each gameweek, given those gameweeks' deadlines."""
    if player.chance_of_playing_next_round is not None:
        chance_next = player.chance_of_playing_next_round / 100
    else:
        chance_next = 0.0 if player.status in OUT else 1.0
    back = return_date(player.news, today) if player.status != "a" else None

    out = []
    for i, deadline in enumerate(deadlines):
        if i == 0:
            out.append(chance_next)
        elif back is not None:
            out.append(1.0 if back <= (deadline + GAMEWEEK_GRACE).date() else 0.0)
        elif player.status in OUT:
            out.append(chance_next)  # out with no return date: assume still out
        else:
            out.append(1.0)  # available or doubtful: doubts are usually short-term knocks
    return out
