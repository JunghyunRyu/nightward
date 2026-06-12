"""Diagnose what is volatile behind CHANGED behaviors and suggest scrub rules.

A noisy gate is a dead gate: when a behavior keeps flipping to CHANGED, the
cause is usually one volatile field (timestamp, counter, request id). This
walks approved vs received payloads, names the drifting paths, and suggests
the matching `scrub.register_field(...)` line. Strictly read-only: it never
edits the store, applies a rule, or moves the boundary — taming noise stays a
human decision, exactly like approve.
"""
from __future__ import annotations

import re
from typing import Any

from .behavior import Behavior
from .diff import CHANGED, compare

ROOT = "$"
_INDEX_SUFFIX = re.compile(r"\[\d+\]$")


def changed_paths(old: Any, new: Any, prefix: str = "") -> tuple[list[str], list[str]]:
    """Return (volatile, structural) dotted paths where old and new differ.

    volatile   = same shape, different value -> tameable with register_field
    structural = keys / list length / container type changed -> a real shape
                 change; scrubbing can't (and shouldn't) hide it
    """
    path = prefix or ROOT
    if isinstance(old, dict) and isinstance(new, dict):
        volatile: list[str] = []
        structural: list[str] = []
        for key in sorted(set(old) | set(new)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in old or key not in new:
                structural.append(child)
            else:
                v, s = changed_paths(old[key], new[key], child)
                volatile += v
                structural += s
        return volatile, structural
    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            return [], [f"{path}[]"]
        volatile, structural = [], []
        for i, (o, n) in enumerate(zip(old, new, strict=True)):
            v, s = changed_paths(o, n, f"{prefix}[{i}]" if prefix else f"{ROOT}[{i}]")
            volatile += v
            structural += s
        return volatile, structural
    if isinstance(old, dict | list) or isinstance(new, dict | list):
        return ([], [path]) if old != new else ([], [])
    return ([path], []) if old != new else ([], [])


def _leaf_key(path: str) -> str | None:
    """The dict key a register_field rule would target, or None (e.g. root '$')."""
    leaf = _INDEX_SUFFIX.sub("", path.rsplit(".", 1)[-1])
    while _INDEX_SUFFIX.search(leaf):
        leaf = _INDEX_SUFFIX.sub("", leaf)
    return None if not leaf or leaf == ROOT else leaf


def diagnose(baseline: dict[str, Behavior], pending: dict[str, Behavior]) -> dict:
    """Per-behavior drift paths + ranked register_field suggestions."""
    changed = [c.name for c in compare(baseline, pending) if c.kind == CHANGED]
    behaviors: dict[str, dict] = {}
    field_hits: dict[str, int] = {}
    for name in changed:
        volatile, structural = changed_paths(baseline[name].payload, pending[name].payload)
        behaviors[name] = {"volatile": volatile, "structural": structural}
        for p in volatile:
            leaf = _leaf_key(p)
            if leaf:
                field_hits[leaf] = field_hits.get(leaf, 0) + 1
    ranked = sorted(field_hits.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "changed": changed,
        "behaviors": behaviors,
        "volatile_fields": dict(ranked),
        "suggestions": [f'scrub.register_field("{field}")' for field, _ in ranked],
    }
