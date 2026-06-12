"""Aggregate raw changes into a blast-radius report.

This is the layer that sets nightward apart from a plain snapshot library:
"AI touched A → here are the N behaviors that moved, grouped by feature."
"""
from __future__ import annotations

from collections import defaultdict

from .diff import CHANGED, NEW, REMOVED, UNCHANGED, Change


def aggregate(changes: list[Change]) -> dict:
    unapproved = [c for c in changes if c.kind != UNCHANGED]

    by_group: dict[str, list[dict]] = defaultdict(list)
    for c in unapproved:
        by_group[c.group or "(ungrouped)"].append(c.to_dict() | {"diff": c.diff_text})

    counts = {
        "total": len(changes),
        "unchanged": sum(1 for c in changes if c.kind == UNCHANGED),
        "new": sum(1 for c in changes if c.kind == NEW),
        "changed": sum(1 for c in changes if c.kind == CHANGED),
        "removed": sum(1 for c in changes if c.kind == REMOVED),
        # fingerprint mismatches an LLM judge ruled equivalent (audit visibility)
        "judged_same": sum(1 for c in changes if c.kind == UNCHANGED and c.judged),
    }

    return {
        "boundary": "intact" if not unapproved else "breached",
        "unapproved": len(unapproved),
        "counts": counts,
        "blast_radius": {g: items for g, items in sorted(by_group.items())},
    }
