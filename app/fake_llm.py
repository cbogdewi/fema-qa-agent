"""Deterministic stand-in for the LLM, used by unit tests and offline demos.

It recognises a handful of question shapes and emits the SQL a good model would.
"""

from __future__ import annotations

import json
import re

from .agent import ANSWER_SYSTEM


class FakeLLM:
    name = "fake:deterministic"

    def complete_json(self, system: str, user: str) -> dict:
        q = re.search(r"<question>(.*?)</question>", user, re.S)
        question = (q.group(1) if q else user).lower()

        if system == ANSWER_SYSTEM:
            data = json.loads(user.split("SQL result (JSON):\n", 1)[1])
            if not data["rows"]:
                return {"answer": "No matching records were found."}
            first = data["rows"][0]
            return {"answer": f"{data['columns'][-1]}: {first[-1]}"}

        if any(w in question for w in ("ignore previous", "system prompt", "drop table", "weather", "recipe")):
            return {"on_topic": False, "sql": None, "reason": "out of scope"}
        if "per year" in question or "by year" in question:
            return {
                "on_topic": True,
                "sql": "SELECT EXTRACT(year FROM declaration_date) AS year, "
                "COUNT(DISTINCT disaster_number) AS disasters FROM declarations GROUP BY 1 ORDER BY 1",
                "reason": "trend",
            }
        m = re.search(r"\bin ([a-z]{2})\b", question)
        if "how many" in question and m:
            return {
                "on_topic": True,
                "sql": "SELECT COUNT(DISTINCT disaster_number) AS disasters FROM declarations "
                f"WHERE state = '{m.group(1).upper()}'",
                "reason": "count by state",
            }
        if "bad sql" in question:
            return {"on_topic": True, "sql": "SELECT nope FROM declarations", "reason": "test"}
        return {
            "on_topic": True,
            "sql": "SELECT COUNT(DISTINCT disaster_number) AS disasters FROM declarations",
            "reason": "default",
        }
