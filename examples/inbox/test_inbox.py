"""Capture inbox aggregates as nightward behaviors.

No expected values are hand-written: we capture what ``aggregate.py`` actually
produces for a fixed 50-email synthetic inbox, approve it once, then gate every
later change against that baseline. Each behavior lands in its own ``group`` so
the blast radius shows exactly which analysis axis moved.
"""
from aggregate import (
    attachments_summary,
    by_domain,
    by_label,
    by_sender,
    by_weekday,
    summary,
    threads,
)
from emails import generate_emails

INBOX = generate_emails(50, seed=42)


def test_summary(behavior):
    behavior("inbox_summary", summary(INBOX), group="summary")


def test_by_sender(behavior):
    behavior("by_sender", by_sender(INBOX), group="senders")


def test_by_domain(behavior):
    behavior("by_domain", by_domain(INBOX), group="domains")


def test_by_weekday(behavior):
    behavior("by_weekday", by_weekday(INBOX), group="timeline")


def test_by_label(behavior):
    behavior("by_label", by_label(INBOX), group="labels")


def test_threads(behavior):
    behavior("threads", threads(INBOX), group="threads")


def test_attachments(behavior):
    behavior("attachments_summary", attachments_summary(INBOX), group="attachments")
