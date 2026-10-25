from app.rules import load_rules
from app.rules.checks import check_against_bootstrap, chip_windows
from tests import factories as f

RULES = load_rules("2026_27")


def test_config_loads_with_expected_squad_shape():
    assert RULES.squad.positions == {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
    assert sum(RULES.squad.positions.values()) == RULES.squad.size
    assert RULES.transfers.max_banked == 5
    assert RULES.transfers.hit_cost == 4
    assert len(RULES.chips.windows) == 8


def test_config_matches_a_bootstrap_with_this_seasons_values():
    assert check_against_bootstrap(RULES, f.bootstrap()) == []


def test_reports_a_changed_club_limit_and_banked_cap():
    changed = f.GAME_SETTINGS | {"squad_team_limit": 4, "max_extra_free_transfers": 1}
    problems = check_against_bootstrap(RULES, f.bootstrap(game_settings=changed))
    assert problems == [
        "max players per club: season_rules says 3, FPL API says 4",
        "max banked free transfers: season_rules says 5, FPL API says 2",
    ]


def test_reports_changed_chip_windows():
    chips = [c | {"stop_event": 18} if c["stop_event"] == 19 else c for c in f.API_CHIPS]
    problems = check_against_bootstrap(RULES, f.bootstrap(chips=chips))
    assert len(problems) == 1 and problems[0].startswith("chip windows")


def test_chip_windows_come_from_the_api_and_are_numbered_by_half():
    windows = chip_windows(RULES, f.bootstrap())
    freehits = [(w.half, w.start, w.end) for w in windows if w.name == "freehit"]
    assert freehits == [(1, 2, 19), (2, 20, 38)]


def test_chip_windows_fall_back_to_config_when_the_api_drops_them():
    assert chip_windows(RULES, f.bootstrap(chips=[])) == RULES.chips.windows
    problems = check_against_bootstrap(RULES, f.bootstrap(chips=[]))
    assert problems == ["FPL API no longer lists chips; using chip windows from season_rules"]
