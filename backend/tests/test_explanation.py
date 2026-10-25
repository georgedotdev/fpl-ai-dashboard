import httpx
import pytest
import respx

from app.explanation import explain
from app.explanation.check import check_explanation
from app.explanation.facts import build_facts
from app.explanation.local_model import LocalModelError, OllamaExplainer
from app.explanation.templates import template_explanation
from app.manager.state import Sourced
from app.optimization.recommend import (
    GameweekRecommendation,
    MovePlan,
    PickedPlayer,
    PlayerFacts,
    Recommendations,
    RecommendedPlan,
)


def facts_player(pid, name, price, xp, status="a", news="", difficulty=3):
    return PlayerFacts(
        player_id=pid, web_name=name, team_short_name="AAA", position="FWD", price=price,
        xp=xp, xp_total=round(sum(xp), 2), availability=[1.0] * len(xp), status=status, news=news,
        fixtures=[["BBB (H)"]] * len(xp), fixture_difficulty=[[difficulty]] * len(xp),
    )


def picked(pid, name, xp):
    return PickedPlayer(player_id=pid, web_name=name, position="FWD", team_short_name="AAA", xp=xp, fixtures=["BBB (H)"])


def recommendations(moves=(), hits=0, chip=None, free_transfers=1, next_ft=2):
    """A two-gameweek plan for GW9-10 with the given first-week moves."""
    def gw(n, moves, ft, hits=0, chip=None):
        return GameweekRecommendation(
            gameweek=n, free_transfers=ft, hits=hits, hit_points=hits * 4, chip=chip, moves=list(moves),
            captain=picked(1, "Haaland", 9.2), vice_captain=picked(2, "Gabriel", 7.4),
            lineup=[], bench=[], expected_points=60.0, bank=8,
        )
    plan = RecommendedPlan(
        rank=1, headline="", expected_points=120.0, gain_vs_no_transfers=6.3,
        gameweeks=[gw(9, moves, free_transfers, hits, chip), gw(10, [], next_ft)],
    )
    return Recommendations(
        team_id=42, model="baseline", gameweeks=[9, 10], decay=0.85,
        bank=Sourced(value=8, source="api"), free_transfers=Sourced(value=free_transfers, source="derived"),
        squad_gameweek=8, no_transfers_expected_points=113.7, plans=[plan], chips=[], notes=[],
    ), plan


WATKINS_TO_ISAK = MovePlan(
    player_out=facts_player(10, "Watkins", 85, [1.5, 3.0], status="d", news="Knock - 50% chance of playing", difficulty=4),
    player_in=facts_player(11, "Isak", 88, [6.0, 6.2], difficulty=2),
    xp_gain=7.7,
)


def test_template_explains_a_transfer_using_only_facts():
    recs, plan = recommendations(moves=[WATKINS_TO_ISAK])
    facts = build_facts(recs, plan)
    text = template_explanation(facts)
    assert "Watkins → Isak (+7.7 xP over GW9-GW10)" in text
    assert "Isak (AAA, £8.8m) is projected 12.2 xP to Watkins's 4.5" in text
    assert "Watkins is doubtful (Knock - 50% chance of playing) and Isak has 2 easy fixtures" in text
    assert "£0.8m in the bank" in text
    assert "Captain Haaland (BBB (H), 9.2 xP)" in text
    assert check_explanation(text, facts) == []


def test_template_for_rolling_the_transfer():
    recs, plan = recommendations()
    text = template_explanation(build_facts(recs, plan))
    assert "roll your free transfer and have 2 next gameweek" in text


def test_template_mentions_chip_and_hit():
    recs, plan = recommendations(moves=[WATKINS_TO_ISAK], hits=1, chip="Bench Boost", free_transfers=0, next_ft=1)
    facts = build_facts(recs, plan)
    text = template_explanation(facts)
    assert text.startswith("Play your Bench Boost this gameweek.")
    assert "plus 1 hit (−4 points)" in text
    assert check_explanation(text, facts) == []


def test_check_rejects_invented_numbers_and_missing_players():
    recs, plan = recommendations(moves=[WATKINS_TO_ISAK])
    facts = build_facts(recs, plan)
    assert check_explanation("Swap Watkins for Isak: +7.7 xP.", facts) == []
    assert check_explanation("Swap Watkins for Isak: +9.5 xP.", facts) == [
        "Mentions numbers that aren't in the facts: 9.5"
    ]
    assert check_explanation("Bring in Isak.", facts) == ["Doesn't mention Watkins, who the plan sells."]


class FakeLocal:
    model = "fake-3b"

    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error

    def explain(self, facts):
        if self.error:
            raise LocalModelError(self.error)
        return self.reply


def test_explain_uses_the_local_model_when_its_text_passes():
    recs, plan = recommendations(moves=[WATKINS_TO_ISAK])
    result = explain(recs, plan, FakeLocal("Watkins is doubtful, so swap him for Isak (+7.7 xP)."))
    assert result.source == "local_model" and result.model == "fake-3b" and result.note is None


def test_explain_falls_back_when_the_local_model_invents_a_number():
    recs, plan = recommendations(moves=[WATKINS_TO_ISAK])
    result = explain(recs, plan, FakeLocal("Swap Watkins for Isak, who scores 15 a week."))
    assert result.source == "template"
    assert "failed a check" in result.note and "15" in result.note


def test_explain_falls_back_when_the_local_model_is_down():
    recs, plan = recommendations(moves=[WATKINS_TO_ISAK])
    result = explain(recs, plan, FakeLocal(error="Local model unreachable: refused."))
    assert result.source == "template" and result.note.startswith("Local model unreachable")


def test_explain_without_a_local_model_uses_the_template_silently():
    recs, plan = recommendations()
    result = explain(recs, plan, None)
    assert result.source == "template" and result.note is None


@respx.mock
def test_ollama_explainer_calls_the_chat_api():
    route = respx.post("http://ollama.test/api/chat").respond(json={"message": {"role": "assistant", "content": " Hi. "}})
    explainer = OllamaExplainer("http://ollama.test", "tiny-model")
    assert explainer.explain({"a": 1}) == "Hi."
    sent = route.calls[0].request
    body = httpx.Response(200, content=sent.content).json()
    assert body["model"] == "tiny-model" and body["stream"] is False
    assert body["messages"][1]["content"] == '{"a": 1}'


@respx.mock
def test_ollama_errors_become_local_model_errors():
    respx.post("http://ollama.test/api/chat").respond(404, text="model not found")
    with pytest.raises(LocalModelError, match="404"):
        OllamaExplainer("http://ollama.test", "missing").explain({})
