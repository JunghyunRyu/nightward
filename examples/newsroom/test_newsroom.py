"""Captures: exact gate for facts, semantic gate for the AI brief."""
from newsroom import STORIES, count_by_section, daily_brief, top_story


def test_section_counts(behavior):
    behavior("section_counts", count_by_section(STORIES), group="facts")


def test_top_story(behavior):
    behavior("top_story", top_story(STORIES), group="facts")


def test_daily_brief(behavior):
    # Free text: fingerprints differ on every rewording, meaning often doesn't.
    # semantic=True lets a judge model rule on equivalence (it cannot approve).
    behavior("daily_brief", daily_brief(STORIES), group="brief", semantic=True)
