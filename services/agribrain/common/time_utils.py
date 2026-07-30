from datetime import datetime, timezone
from typing import Optional

def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensures a datetime object is UTC-aware.
    If dt is naive, assumes UTC and sets tzinfo=timezone.utc.
    If dt is already timezone-aware, converts it to UTC.
    Returns None if dt is None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
