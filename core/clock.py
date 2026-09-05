"""Wall-clock helpers so chat messages keep conversational order.

Postgres ``now()`` is transaction-scoped: a customer ingest and the
assistant reply created in the same commit would share one timestamp,
and ``ORDER BY created_at`` could put the question above the answer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def message_time(after: datetime | None = None) -> datetime:
    """Monotonic-enough UTC time strictly after ``after`` when given."""
    now = utc_now()
    if after is None:
        return now
    point = after if after.tzinfo is not None else after.replace(tzinfo=timezone.utc)
    floor = point + timedelta(milliseconds=1)
    return now if now > floor else floor
