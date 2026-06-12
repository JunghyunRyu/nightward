"""Nightward error types — surfaced as clean CLI messages, never tracebacks."""
from __future__ import annotations


class NightwardError(Exception):
    """Any user-facing nightward failure (bad input, missing behavior, etc.)."""
