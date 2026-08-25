"""The versioned EUR/USD session policy used by historical data rules."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .session_policy import OANDA_EUR_USD_POLICY

MINUTE = timedelta(minutes=1)
SESSION_POLICY = OANDA_EUR_USD_POLICY.version


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
    """Compatibility adapter over the single versioned policy seam."""
    start = _utc_minute(start)
    classification, reason, _version = OANDA_EUR_USD_POLICY.classify_minute(start)
    return SessionMinute(start, classification == "EXPECTED_DATA", reason)


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
                OANDA_EUR_USD_POLICY.classify_minute(
                    cursor + MINUTE * offset
                )[0]
                == "EXPECTED_DATA"
                for offset in range(15)
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
            OANDA_EUR_USD_POLICY.classify_minute(cursor + MINUTE * offset)[0]
            == "EXPECTED_DATA"
            for offset in range(15)
        ):
            count += 1
    return cursor, requested_end


__all__ = [
    "OANDA_EUR_USD_POLICY",
    "SESSION_POLICY",
    "SessionMinute",
    "classify_minute",
    "eligible_m15_windows",
    "is_session_open_minute",
    "required_warmup_range",
]
