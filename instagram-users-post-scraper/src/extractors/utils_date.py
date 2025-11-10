from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

def parse_instagram_timestamp(value: Any) -> Optional[_dt.datetime]:
    """
    Convert Instagram's timestamp formats into a timezone-aware UTC datetime.

    Expected inputs:
        - Unix timestamp in seconds (int or str)
        - ISO 8601 string (fallback)
    """
    if value is None:
        return None

    # Numeric unix timestamp (seconds)
    try:
        if isinstance(value, (int, float)):
            return _dt.datetime.fromtimestamp(float(value), tz=_dt.timezone.utc)

        if isinstance(value, str) and value.isdigit():
            return _dt.datetime.fromtimestamp(float(value), tz=_dt.timezone.utc)
    except (OverflowError, OSError, ValueError):
        pass

    # Fallback: attempt to parse ISO-8601-like strings
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = _dt.datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_dt.timezone.utc)
                return dt.astimezone(_dt.timezone.utc)
            except ValueError:
                continue

    return None

def format_datetime_readable(dt: Optional[_dt.datetime]) -> Optional[str]:
    """
    Format datetime to a human-readable string "YYYY-MM-DD HH:MM" in UTC.
    """
    if dt is None:
        return None
    dt_utc = dt.astimezone(_dt.timezone.utc)
    return dt_utc.strftime("%Y-%m-%d %H:%M")

def to_iso8601(dt: Optional[_dt.datetime]) -> Optional[str]:
    """
    Return ISO-8601 formatted string from datetime, or None.
    """
    if dt is None:
        return None
    return dt.astimezone(_dt.timezone.utc).isoformat()