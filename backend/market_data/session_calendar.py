"""The versioned EUR/USD session policy used by historical data rules."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.domain.market_data import SESSION_POLICY

NEW_YORK = ZoneInfo("America/New_York")
MINUTE = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class SessionMinute:
    start: datetime
    open: bool
    reason: str | None = None


def _utc_minute(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("session times must be timezone-aware UTC")
    if value.second or value.microsecond:
        raise ValueError("session times must be minute-aligned")
    return value


def classify_minute(start: datetime) -> SessionMinute:
    """Classify a UTC minute without applying holiday assumptions."""
    start = _utc_minute(start)
    local = start.astimezone(NEW_YORK)
    weekday = local.weekday()  # Monday=0, Sunday=6
    local_minute = local.hour * 60 + local.minute
    friday_close = 16 * 60 + 59
    sunday_open = 17 * 60 + 5
    daily_break = 16 * 60 + 59 <= local.hour * 60 + local.minute < 17 * 60 + 5
    weekend = (
        (weekday == 4 and local_minute >= friday_close)
        or weekday == 5
        or (weekday == 6 and local_minute < sunday_open)
    )
    if weekend:
        return SessionMinute(start, False, "WEEKEND")
    if daily_break:
        return SessionMinute(start, False, "DAILY_BREAK")
    return SessionMinute(start, True)


def is_session_open_minute(start: datetime) -> bool:
    return classify_minute(start).open


def eligible_m15_windows(
    start: datetime, end: datetime
) -> tuple[tuple[datetime, datetime], ...]:
    """Return aligned windows containing at least one eligible minute."""
    start = _utc_minute(start)
    end = _utc_minute(end)
    if end <= start:
        raise ValueError("range must be positive")
    cursor = start - timedelta(minutes=start.minute % 15)
    windows: list[tuple[datetime, datetime]] = []
    while cursor < end:
        window_end = cursor + timedelta(minutes=15)
        if window_end > start and cursor < end:
            if any(
                is_session_open_minute(cursor + MINUTE * offset) for offset in range(15)
            ):
                windows.append((cursor, window_end))
        cursor = window_end
    return tuple(windows)


def required_warmup_range(
    requested_start: datetime,
    requested_end: datetime,
    warm_up_m15_bars: int,
) -> tuple[datetime, datetime]:
    """Extend a range backward by eligible, rather than calendar, M15 windows."""
    requested_start = _utc_minute(requested_start)
    requested_end = _utc_minute(requested_end)
    if requested_end <= requested_start:
        raise ValueError("range must be positive")
    if type(warm_up_m15_bars) is not int or warm_up_m15_bars < 0:
        raise ValueError("warm_up_m15_bars must be a non-negative integer")
    cursor = requested_start - timedelta(minutes=requested_start.minute % 15)
    if warm_up_m15_bars == 0:
        return requested_start, requested_end
    count = 0
    while count < warm_up_m15_bars:
        cursor -= timedelta(minutes=15)
        if any(
            is_session_open_minute(cursor + MINUTE * offset) for offset in range(15)
        ):
            count += 1
    return cursor, requested_end


__all__ = [
    "NEW_YORK",
    "SESSION_POLICY",
    "SessionMinute",
    "classify_minute",
    "eligible_m15_windows",
    "is_session_open_minute",
    "required_warmup_range",
]
