"""Pytest plugin: capture behaviors during a normal test run.

We piggyback on pytest (discovery, fixtures, parametrization, CI) instead of
building a runner. Tests opt in by requesting the `behavior` fixture and calling
it. Behaviors are flushed to .nightward/pending only when --nightward-record is set.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from .core.baseline import Store
from .core.behavior import Behavior, validate_name
from .errors import NightwardError
from .scrub import scrub


class Recorder:
    def __init__(self) -> None:
        self.behaviors: list[Behavior] = []
        self._seen: set[str] = set()

    def add(self, name: str, value, group: str | None = None,
            semantic: bool = False) -> None:
        validate_name(name)
        if name in self._seen:
            raise NightwardError(
                f"duplicate behavior name {name!r}: each captured behavior must be unique"
            )
        self._seen.add(name)
        # scrub() -> canonical_json may raise NightwardError on bad payloads;
        # let it surface so the offending test fails loudly.
        self.behaviors.append(
            Behavior(name=name, payload=scrub(value), group=group, semantic=semantic)
        )


def pytest_addoption(parser):
    group = parser.getgroup("nightward")
    group.addoption("--nightward-record", action="store_true", default=False,
                    help="Record behaviors to the nightward pending store")
    group.addoption("--nightward-dir", action="store", default=".nightward",
                    help="Nightward storage directory (default: .nightward)")


def pytest_configure(config):
    config._nightward_recorder = Recorder()


@pytest.fixture
def behavior(request):
    """Capture a named behavior:  behavior("checkout_total", result, group="billing")

    semantic=True opts the behavior into LLM-judge equivalence (v0.2): on a
    fingerprint mismatch the configured judge may rule the change SAME-by-meaning.
    Use it only for nondeterministic free text; deterministic payloads stay exact.
    """
    rec = request.config._nightward_recorder

    def capture(name: str, value, *, group: str | None = None,
                semantic: bool = False) -> None:
        rec.add(name, value, group=group, semantic=semantic)

    return capture


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if not config.getoption("--nightward-record"):
        return
    rec = getattr(config, "_nightward_recorder", None)
    if rec is None:
        return
    store = Store(Path(config.getoption("--nightward-dir")))
    store.ensure()
    store.clear_pending()
    for b in rec.behaviors:
        store.write_pending(b)

    # Skipped tests don't capture their behavior -> it shows up as a false
    # REMOVED. Record the counts so `nightward run` can warn about it.
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    skipped = len(reporter.stats.get("skipped", [])) if reporter else 0
    failed = len(reporter.stats.get("failed", [])) if reporter else 0
    store.write_run_meta({"skipped": skipped, "failed": failed})
