from datetime import UTC, datetime


def parse_time(raw: str) -> str | None:
    """Parse HH:MM 24h string and return normalized value."""
    parts = raw.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    hours, minutes = parts
    hour_int, minute_int = int(hours), int(minutes)
    if not (0 <= hour_int <= 23 and 0 <= minute_int <= 59):
        return None
    return f"{hour_int:02d}:{minute_int:02d}"


def utc_now():
    return datetime.now(UTC)
