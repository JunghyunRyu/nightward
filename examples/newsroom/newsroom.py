"""A tiny newsroom: deterministic facts + a nondeterministic AI brief.

The facts layer is pure computation — nightward's exact fingerprint gate fits
it perfectly. The daily brief simulates an LLM summary: same meaning, but the
wording drifts between runs (toggle with NEWSROOM_REWRITE=1). That drift is
what `behavior(..., semantic=True)` + `nightward run --judge` exists for.
"""
from __future__ import annotations

import os

STORIES = [
    {"id": "s1", "section": "markets", "title": "Chips slide for a third day", "views": 8120},
    {"id": "s2", "section": "markets", "title": "Record IPO prices on Friday", "views": 12400},
    {"id": "s3", "section": "science", "title": "Chip-scale laser matches lab rigs", "views": 3010},
    {"id": "s4", "section": "sports", "title": "Finals streak ends in game 3", "views": 9900},
]


def count_by_section(stories: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for s in stories:
        counts[s["section"]] = counts.get(s["section"], 0) + 1
    return dict(sorted(counts.items()))


def top_story(stories: list[dict]) -> dict:
    best = max(stories, key=lambda s: s["views"])
    return {"id": best["id"], "title": best["title"], "views": best["views"]}


def daily_brief(stories: list[dict]) -> str:
    """Simulated LLM output: two rewordings of the same facts."""
    top = top_story(stories)["title"]
    n = len(stories)
    if os.environ.get("NEWSROOM_REWRITE") == "1":
        return f"Today's {n} stories are led by '{top}', with markets dominating the cycle."
    return f"Markets dominate today's cycle: {n} stories, led by '{top}'."
