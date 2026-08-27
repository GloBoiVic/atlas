"""Pure, versioned expected-session policy for the initial OANDA instrument.

The policy deliberately knows only EUR/USD at OANDA.  It classifies a UTC
minute from declared schedule rules; it never consults prices, a database, or
the provider.  See ``oanda_session_policy_provenance.md`` for the documentary
source pin and outstanding source-verification work.

Documentary metadata (all pending source verification): URL
``OANDA_DOC_PENDING``; title ``OANDA_DOC_PENDING``; retrieval date
``2026-08-24``; effective interval ``OANDA_DOC_PENDING``; timezone
``America/New_York``; reasons ``WEEKLY_CLOSURE`` and
``PROVIDER_MAINTENANCE_ROLLOVER``. Holiday/session exceptions use the same
effective-dated metadata once OANDA notices are pinned.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo

EXPECTED_DATA: Final[str] = "EXPECTED_DATA"
UNAVAILABLE_SESSION: Final[str] = "UNAVAILABLE_SESSION"
OANDA_FX_NY_V1: Final[str] = "OANDA_FX_NY_V1"
OANDA_FX_NY_V2: Final[str] = "OANDA_FX_NY_V2"
NEW_YORK_TIMEZONE: Final[str] = "America/New_York"


def _utc_minute(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("session times must be timezone-aware UTC")
    if value.second or value.microsecond:
        raise ValueError("session times must be minute-aligned")
    return value


@dataclass(frozen=True, slots=True)
class SessionException:
    """An immutable, effective-dated local session override.

    Dates and minutes are local to the policy timezone.  A whole-day holiday
    is represented by ``start_minute=0, end_minute=1440``.  The initial V1
    table is intentionally empty until OANDA notices are source-pinned.
    """

    effective_start: date
    effective_end: date
    start_minute: int
    end_minute: int
    classification: str
    reason: str

    def __post_init__(self) -> None:
        if self.effective_end < self.effective_start:
            raise ValueError("exception effective interval must be ordered")
        if not 0 <= self.start_minute < self.end_minute <= 1440:
            raise ValueError("exception minutes must be within a local day")
        if self.classification not in (EXPECTED_DATA, UNAVAILABLE_SESSION):
            raise ValueError("unsupported session exception classification")
        if not self.reason:
            raise ValueError("session exception reason is required")


@dataclass(frozen=True, slots=True)
class ExpectedSessionPolicy:
    """Immutable UTC-minute classification rules for one venue instrument."""

    version: str
    timezone: str
    maintenance_start_minute: int
    maintenance_end_minute: int
    exceptions: tuple[SessionException, ...] = ()

    def __post_init__(self) -> None:
        if not self.version or not self.timezone:
            raise ValueError("policy version and timezone are required")
        if not 0 <= self.maintenance_start_minute < self.maintenance_end_minute <= 1440:
            raise ValueError("maintenance interval must be within a local day")
        if (
            tuple(
                sorted(
                    self.exceptions,
                    key=lambda item: (item.effective_start, item.start_minute),
                )
            )
            != self.exceptions
        ):
            raise ValueError("session exceptions must be deterministically ordered")

    def classify_minute(
        self, utc_minute: datetime
    ) -> tuple[str, str, str]:
        """Return ``(classification, stable reason, policy version)``."""
        utc_minute = _utc_minute(utc_minute)
        local = utc_minute.astimezone(ZoneInfo(self.timezone))
        local_date = local.date()
        local_minute = local.hour * 60 + local.minute

        for exception in self.exceptions:
            if exception.effective_start <= local_date <= exception.effective_end:
                if exception.start_minute <= local_minute < exception.end_minute:
                    return exception.classification, exception.reason, self.version

        # These are local civil-time rules, not fixed UTC offsets; ZoneInfo
        # therefore applies the applicable EST/EDT transition automatically.
        if local.weekday() == 5 or (
            local.weekday() == 4 and local_minute >= self.maintenance_start_minute
        ) or (
            local.weekday() == 6 and local_minute < self.maintenance_end_minute
        ):
            return UNAVAILABLE_SESSION, "WEEKLY_CLOSURE", self.version
        if self.maintenance_start_minute <= local_minute < self.maintenance_end_minute:
            return UNAVAILABLE_SESSION, "PROVIDER_MAINTENANCE_ROLLOVER", self.version
        return EXPECTED_DATA, "EXPECTED_PROVIDER_SESSION", self.version


# OANDA EUR/USD V2.  OANDA's 2025 holiday notice documents FX opening late at
# 17:05 ET on 1 January and 25 December, and closing at 16:59 ET on 24 and 31
# December.  The exception intervals begin after the regular 16:59–17:05
# rollover window, so the existing daily rule remains authoritative elsewhere.
# A semantic change is represented by a new policy version; old snapshots keep
# their V1 meaning.
OANDA_EUR_USD_POLICY: Final[ExpectedSessionPolicy] = ExpectedSessionPolicy(
    version=OANDA_FX_NY_V2,
    timezone=NEW_YORK_TIMEZONE,
    maintenance_start_minute=16 * 60 + 59,
    maintenance_end_minute=17 * 60 + 5,
    exceptions=(
        SessionException(date(2024, 12, 31), date(2024, 12, 31), 17 * 60 + 5,
                         1440, UNAVAILABLE_SESSION, "HOLIDAY_CLOSURE"),
        SessionException(date(2025, 1, 1), date(2025, 1, 1), 0, 17 * 60 + 5,
                         UNAVAILABLE_SESSION, "HOLIDAY_CLOSURE"),
        SessionException(date(2025, 12, 24), date(2025, 12, 24), 16 * 60 + 59,
                         1440, UNAVAILABLE_SESSION, "HOLIDAY_CLOSURE"),
        SessionException(date(2025, 12, 25), date(2025, 12, 25), 0, 17 * 60 + 5,
                         UNAVAILABLE_SESSION, "HOLIDAY_CLOSURE"),
        SessionException(date(2025, 12, 31), date(2025, 12, 31), 16 * 60 + 59,
                         1440, UNAVAILABLE_SESSION, "HOLIDAY_CLOSURE"),
    ),
)
DEFAULT_POLICY: Final[ExpectedSessionPolicy] = OANDA_EUR_USD_POLICY


__all__ = [
    "EXPECTED_DATA",
    "UNAVAILABLE_SESSION",
    "OANDA_FX_NY_V1",
    "OANDA_FX_NY_V2",
    "ExpectedSessionPolicy",
    "OANDA_EUR_USD_POLICY",
    "DEFAULT_POLICY",
    "SessionException",
]
