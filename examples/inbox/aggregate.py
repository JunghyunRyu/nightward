"""Pure aggregations over an inbox (a list of email dicts). No I/O, no randomness.

Each function returns a JSON-serializable summary that nightward captures as one
behavior. Correctness is never asserted here: nightward locks whatever these
functions actually produce, and a human approves it once as the baseline.
"""
from __future__ import annotations

import datetime
from collections import Counter, defaultdict

_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def summary(emails: list[dict]) -> dict:
    """Inbox-wide totals: counts, unique entities, attachment volume."""
    return {
        "total": len(emails),
        "unread": sum(1 for e in emails if not e["is_read"]),
        "read": sum(1 for e in emails if e["is_read"]),
        "important": sum(1 for e in emails if e["is_important"]),
        "unique_senders": len({e["from"]["addr"] for e in emails}),
        "unique_domains": len({e["domain"] for e in emails}),
        "thread_count": len({e["thread_id"] for e in emails}),
        "total_attachments": sum(len(e["attachments"]) for e in emails),
        "total_size_bytes": sum(e["size_bytes"] for e in emails),
        "total_attachment_bytes": sum(
            a["size"] for e in emails for a in e["attachments"]
        ),
    }


def by_sender(emails: list[dict], top: int = 5) -> list[dict]:
    """Top senders by message count."""
    counts = Counter(e["from"]["addr"] for e in emails)
    return [{"sender": s, "count": n} for s, n in counts.most_common(top)]


def by_domain(emails: list[dict]) -> list[dict]:
    """Messages per sender domain, with share of the inbox."""
    counts = Counter(e["domain"] for e in emails)
    total = len(emails) or 1
    return [
        {"domain": d, "count": n, "pct": round(100 * n / total, 1)}
        for d, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def by_weekday(emails: list[dict]) -> dict:
    """Message distribution across weekdays (locale-independent)."""
    counts = Counter(
        datetime.date.fromisoformat(e["date"]).weekday() for e in emails
    )
    return {_WEEK[i]: counts.get(i, 0) for i in range(7)}


def by_label(emails: list[dict]) -> dict:
    """Message count per label (an email may carry several)."""
    counts = Counter(label for e in emails for label in e["labels"])
    return dict(sorted(counts.items()))


def threads(emails: list[dict], top: int = 5) -> list[dict]:
    """Largest conversation threads: size and participants."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in emails:
        groups[e["thread_id"]].append(e)
    rows = [
        {
            "thread_id": tid,
            "messages": len(msgs),
            "participants": sorted({m["from"]["addr"] for m in msgs}),
        }
        for tid, msgs in groups.items()
    ]
    rows.sort(key=lambda r: (-r["messages"], r["thread_id"]))
    return rows[:top]


def attachments_summary(emails: list[dict]) -> dict:
    """Attachment counts and byte volume, broken down by file type."""
    by_type: Counter = Counter()
    bytes_by_type: dict[str, int] = defaultdict(int)
    for e in emails:
        for a in e["attachments"]:
            by_type[a["type"]] += 1
            bytes_by_type[a["type"]] += a["size"]
    return {
        "total_count": sum(by_type.values()),
        "by_type": dict(sorted(by_type.items())),
        "bytes_by_type": dict(sorted(bytes_by_type.items())),
    }
