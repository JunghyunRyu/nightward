"""Shared run logic: capture behaviors via pytest, recompute the blast radius.

Used by both `cli.run` (rich console) and the MCP server (JSON) so the two
surfaces report the same measurement. No console output here.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .core.baseline import Store
from .core.blast import aggregate
from .core.diff import compare
from .errors import NightwardError


def make_judge(spec: str | None, store: Store):
    """Build the semantic judge for a 'provider:model' spec (None -> no judge).

    The verdict ledger lives in the store and is meant to be committed — see
    judge.Judge.equivalent.
    """
    if not spec:
        return None
    from .judge import Judge
    return Judge(spec, cache_path=store.root / "judge_verdicts.json")


def judge_from_meta(store: Store):
    """Recreate the judge the last run used, so approve/recompute see the same
    verdicts (cache makes this free and deterministic)."""
    return make_judge(store.load_run_meta().get("judge"), store)


def recompute(store: Store, judge=None) -> dict:
    """Compare pending against baseline, aggregate, persist, and return the report."""
    report = aggregate(compare(store.load_baseline(), store.load_pending(), judge=judge))
    store.write_report(report)
    return report


def _pytest_cmd(path: str, dir: str) -> list[str]:
    # -B: no bytecode cache. Rewriting a test file between runs can otherwise
    # re-import a stale .pyc and silently capture OLD behavior (flaky in CI).
    return [sys.executable, "-B", "-m", "pytest", path,
            "--nightward-record", "--nightward-dir", dir, "-q"]


def execute_run(path: str = ".", dir: str = ".nightward", *,
                capture_output: bool = False, judge_spec: str | None = None) -> dict:
    """Run pytest in a subprocess to capture behaviors, then recompute.

    capture_output=True keeps pytest's stdout off this process's stdout — required
    when called from the MCP stdio server (any stray stdout breaks the protocol).
    judge_spec ('provider:model', or env NIGHTWARD_JUDGE) enables the semantic
    judge for behaviors captured with semantic=True; the spec is persisted in
    run_meta so later approve/recompute reuse the same (cached) verdicts.
    Returns {report, skipped, failed, pytest_returncode}.
    """
    spec = judge_spec or os.environ.get("NIGHTWARD_JUDGE") or None
    result = subprocess.run(_pytest_cmd(path, dir), capture_output=capture_output)
    if result.returncode == 5:
        raise NightwardError(f"pytest collected no tests under {path!r}")
    if result.returncode not in (0, 1):
        raise NightwardError(f"pytest exited with code {result.returncode}; aborting")
    store = Store(Path(dir))
    meta = store.load_run_meta()
    if spec:
        meta["judge"] = spec
    else:
        meta.pop("judge", None)
    store.write_run_meta(meta)
    report = recompute(store, judge=make_judge(spec, store))
    return {
        "report": report,
        "skipped": meta.get("skipped", 0),
        "failed": meta.get("failed", 0),
        "pytest_returncode": result.returncode,
    }
