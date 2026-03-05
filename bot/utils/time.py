from datetime import UTC, datetime


def parse_time(raw: str, minute_step: int | None = None) -> str | None:
    """Parse HH:MM 24h string and return normalized value."""
    parts = raw.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    hours, minutes = parts
    hour_int, minute_int = int(hours), int(minutes)
    if not (0 <= hour_int <= 23 and 0 <= minute_int <= 59):
        return None
    if minute_step and (minute_step <= 0 or minute_int % minute_step != 0):
        return None
    return f"{hour_int:02d}:{minute_int:02d}"


def utc_now():
    return datetime.now(UTC)
