from app.manager.chips import chip_statuses
from app.rules import load_rules
from app.rules.checks import chip_windows
from tests import factories as f

RULES = load_rules("2026_27")
WINDOWS = chip_windows(RULES, f.bootstrap())


def statuses(plays: dict[int, str], planning_gw: int):
    return {(c.chip, c.half): c for c in chip_statuses(WINDOWS, f.chip_plays(plays), planning_gw, RULES)}


def test_nothing_played_early_season():
    s = statuses({}, planning_gw=9)
    assert len(s) == 8
    assert {c.state for (_, half), c in s.items() if half == 1} == {"available"}
    assert {c.state for (_, half), c in s.items() if half == 2} == {"upcoming"}
    assert s[("wildcard", 2)].usable_from_gameweek == 20
    assert s[("wildcard", 1)].label == "Wildcard"


def test_played_chips_are_used_in_the_right_half():
    s = statuses({1: "bboost", 6: "wildcard"}, planning_gw=9)
    assert s[("bboost", 1)].state == "used" and s[("bboost", 1)].played_gameweek == 1
    assert s[("wildcard", 1)].state == "used"
    assert s[("bboost", 2)].state == "upcoming"


def test_unplayed_first_half_chips_expire_after_gw19():
    s = statuses({3: "3xc"}, planning_gw=20)
    assert s[("3xc", 1)].state == "used"
    assert s[("freehit", 1)].state == "expired"
    assert s[("freehit", 2)].state == "available"
    assert s[("freehit", 2)].usable_from_gameweek == 20


def test_first_half_chips_are_still_playable_in_gw19():
    s = statuses({}, planning_gw=19)
    assert s[("freehit", 1)].state == "available"


def test_no_back_to_back_free_hits_across_the_halves():
    s = statuses({19: "freehit"}, planning_gw=20)
    second = s[("freehit", 2)]
    assert second.state == "available"
    assert second.usable_from_gameweek == 21
    assert "GW19" in second.note


def test_back_to_back_rule_only_applies_to_listed_chips():
    s = statuses({19: "bboost"}, planning_gw=20)
    assert s[("bboost", 2)].usable_from_gameweek == 20
