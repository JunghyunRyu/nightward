"""Deterministic synthetic inbox: 50 emails with realistic, varied structure.

Seeding ``random.Random(seed)`` makes ``generate_emails`` fully reproducible, so
nightward can lock the downstream aggregates as a baseline and gate every later
change against them.

Two formatting choices are deliberate, to dodge nightward's scrubber: dates are
emitted as ``YYYY-MM-DD`` (no ``T`` time component) and ids use ``msg-``/``thr-``
prefixes. The scrubber rewrites ISO datetimes and UUIDs to placeholders before
fingerprinting, which would erase the very fields we group by.
"""
from __future__ import annotations

import datetime
import random

_SENDERS = [
    ("Alice Kim", "alice", "acme.com"),
    ("Bob Lee", "bob", "acme.com"),
    ("Carla Diaz", "carla", "globex.com"),
    ("Deepak Rao", "deepak", "globex.com"),
    ("Erin Park", "erin", "initech.com"),
    ("Frank Wu", "frank", "initech.com"),
    ("Grace Hall", "grace", "umbrella.co"),
    ("Hugo Stein", "hugo", "umbrella.co"),
    ("Ivy Chen", "ivy", "hooli.io"),
    ("Jack Ono", "jack", "newsletter.shop"),
]
_LABELS = ["inbox", "work", "promotions", "social", "updates", "finance"]
_SUBJECTS = [
    "Q2 budget review", "Re: deployment window", "Your invoice is ready",
    "Lunch next week?", "Security alert", "Weekly digest",
    "Contract draft v3", "Re: onboarding", "Sale ends tonight", "Standup notes",
]
_SNIPPETS = [
    "Just following up on the thread below.",
    "Please find the attached document for review.",
    "Reminder: this is due by end of week.",
    "Thanks for the quick turnaround earlier.",
    "Let me know if the proposed time works.",
]
_ATTACH_TYPES = ["pdf", "xlsx", "png", "docx", "zip"]
_BASE_DATE = datetime.date(2026, 5, 1)


def generate_emails(n: int = 50, seed: int = 42) -> list[dict]:
    """Build ``n`` synthetic emails deterministically from ``seed``."""
    rng = random.Random(seed)
    threads: list[str] = []
    emails: list[dict] = []
    for i in range(n):
        name, local, domain = rng.choice(_SENDERS)
        if threads and rng.random() < 0.3:
            thread_id = rng.choice(threads)
        else:
            thread_id = f"thr-{len(threads) + 1:03d}"
            threads.append(thread_id)
        date = _BASE_DATE + datetime.timedelta(days=rng.randint(0, 30))
        attachments = []
        for j in range(rng.choices([0, 1, 2, 3], weights=[5, 3, 1, 1])[0]):
            atype = rng.choice(_ATTACH_TYPES)
            attachments.append(
                {"name": f"file{j + 1}.{atype}", "type": atype,
                 "size": rng.randint(10_000, 5_000_000)}
            )
        labels = sorted(rng.sample(_LABELS, rng.randint(1, 2)))
        emails.append(
            {
                "id": f"msg-{i + 1:04d}",
                "thread_id": thread_id,
                "from": {"name": name, "addr": f"{local}@{domain}"},
                "domain": domain,
                "date": date.isoformat(),
                "subject": rng.choice(_SUBJECTS),
                "labels": labels,
                "is_read": rng.random() < 0.6,
                "is_important": rng.random() < 0.2,
                "size_bytes": rng.randint(1_000, 200_000),
                "attachments": attachments,
                "snippet": rng.choice(_SNIPPETS),
            }
        )
    return emails
