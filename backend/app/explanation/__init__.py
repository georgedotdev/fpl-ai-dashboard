"""The explanation layer: turns the optimizer's chosen plan into a few plain-English sentences.

It explains; it never decides. It sees only the plan's facts (app/explanation/facts.py), and
whatever writes the text, a local language model or the template writer, the result must
pass the checks in app/explanation/check.py. If the local model is missing, too slow, or
fails a check, the template version is shown instead and the response says why.
"""

from typing import Literal

from pydantic import BaseModel

from app.explanation.check import check_explanation
from app.explanation.facts import build_facts
from app.explanation.local_model import LocalModelError, OllamaExplainer
from app.explanation.templates import template_explanation
from app.optimization.recommend import Recommendations, RecommendedPlan


class Explanation(BaseModel):
    plan_rank: int
    text: str
    source: Literal["local_model", "template"]
    model: str | None  # the local model's name when it wrote the text
    note: str | None  # why the template was used instead of the local model, if it was
    facts: dict  # exactly what the explanation was allowed to use


def explain(recs: Recommendations, plan: RecommendedPlan, local: OllamaExplainer | None) -> Explanation:
    facts = build_facts(recs, plan)
    note = None
    if local is not None:
        try:
            draft = local.explain(facts)
        except LocalModelError as exc:
            note = f"{exc} Showing the template explanation."
        else:
            problems = check_explanation(draft, facts)
            if not problems:
                return Explanation(
                    plan_rank=plan.rank, text=draft, source="local_model", model=local.model, note=None, facts=facts
                )
            note = f"The local model's draft failed a check ({problems[0]}), so this is the template explanation."

    text = template_explanation(facts)
    problems = check_explanation(text, facts)
    if problems:  # a bug in the templates, not something a user can fix
        raise ValueError(f"Template explanation failed its own checks: {problems}")
    return Explanation(plan_rank=plan.rank, text=text, source="template", model=None, note=note, facts=facts)
