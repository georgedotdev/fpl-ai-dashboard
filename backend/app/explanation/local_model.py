"""Rephrase the facts with a language model running locally under Ollama.

No API key and no per-use cost: the model runs on the same machine (or a server we host).
It gets the facts as JSON and a strict brief, and its answer still has to pass
app/explanation/check.py before anyone sees it.
"""

import json

import httpx

SYSTEM_PROMPT = """\
You explain Fantasy Premier League recommendations to the manager they're for.

An optimizer has already chosen the plan. You're given its facts as JSON. Write 2 to 4 plain
sentences, addressed to the manager as "you", that say what to do this gameweek and why.

Rules:
- Use only the facts given. Every number you write must appear in the facts exactly as given;
  never calculate, round differently, or add new numbers.
- Name every player being sold and bought.
- Don't suggest different moves or question the plan.
- No lists, headings or markdown. "xP" means expected points.
"""


class LocalModelError(Exception):
    pass


class OllamaExplainer:
    def __init__(self, base_url: str, model: str, timeout_s: float = 30.0, http: httpx.Client | None = None):
        self.model = model
        self._http = http or httpx.Client(base_url=base_url, timeout=timeout_s)

    def explain(self, facts: dict) -> str:
        try:
            response = self._http.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "options": {"temperature": 0.2},
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
                    ],
                },
            )
        except httpx.HTTPError as exc:
            raise LocalModelError(f"Local model unreachable: {exc}") from exc
        if response.status_code != 200:
            raise LocalModelError(f"Local model returned {response.status_code}: {response.text[:200]}")
        try:
            return response.json()["message"]["content"].strip()
        except (ValueError, KeyError, TypeError) as exc:
            raise LocalModelError("Local model sent an unexpected response.") from exc
