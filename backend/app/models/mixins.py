from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite has no tz support; values are serialized with a Z)."""
    return datetime.now(UTC).replace(tzinfo=None)
