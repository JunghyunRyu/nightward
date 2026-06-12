"""Shared test fixtures."""
import pytest

from nightward import scrub


@pytest.fixture(autouse=True)
def _isolate_scrubbers():
    """Custom scrubbers are module-global; reset around every test."""
    scrub._reset()
    yield
    scrub._reset()
