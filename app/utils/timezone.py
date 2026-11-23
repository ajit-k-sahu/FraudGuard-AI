from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Target Local Timezone for FraudGuard -AI
LOCAL_TIMEZONE_NAME = "Asia/Kolkata"
LOCAL_TIMEZONE = ZoneInfo(LOCAL_TIMEZONE_NAME)
UTC = timezone.utc

# Default Display Format requested: "21 Nov 2026, 08:14 PM IST"
DEFAULT_IST_FORMAT = "%d %b %Y, %I:%M %p IST"


def to_ist(dt):
    """
    Converts a datetime to Asia/Kolkata (IST).
    - If dt is None, returns None.
    - If dt is a naive datetime, assumes it is stored in UTC (standard SQLite storage)
      and converts it accurately to Asia/Kolkata (+05:30).
    - If dt is already timezone-aware, converts it safely using astimezone.
    - Idempotent: Does not apply double conversion if dt is already in Asia/Kolkata.
    """
    if dt is None:
        return None

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except (ValueError, TypeError):
            return dt

    if not isinstance(dt, datetime):
        return dt

    # If naive datetime, assume UTC from database
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    return dt.astimezone(LOCAL_TIMEZONE)


def format_ist(dt, fmt=DEFAULT_IST_FORMAT, default="N/A"):
    """
    Converts a UTC datetime to Asia/Kolkata and formats it.
    Example output: '21 Nov 2026, 08:14 PM IST'.
    """
    if dt is None:
        return default

    ist_dt = to_ist(dt)
    if isinstance(ist_dt, datetime):
        return ist_dt.strftime(fmt)

    return str(dt)
