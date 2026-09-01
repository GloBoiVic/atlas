"""Timestamp validation for persistence boundaries."""

from datetime import datetime, timedelta


def require_utc(value: object, name: str = "timestamp") -> datetime:
    """Require an actual timezone-aware UTC datetime without normalizing it."""
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise ValueError(f"{name} must be timezone-aware UTC")
    return value


def require_optional_utc(
    value: object, name: str = "timestamp"
) -> datetime | None:
    """Validate a nullable persistence timestamp."""
    if value is None:
        return None
    return require_utc(value, name)


def require_non_decreasing_utc(
    previous: object, current: object, name: str
) -> datetime | None:
    """Validate a nullable UTC timestamp and prevent a persisted regression."""
    previous_value = require_optional_utc(previous, name)
    current_value = require_optional_utc(current, name)
    if (
        previous_value is not None
        and (current_value is None or current_value < previous_value)
    ):
        raise ValueError(f"{name} cannot move backwards")
    return current_value


__all__ = [
    "require_non_decreasing_utc",
    "require_optional_utc",
    "require_utc",
]
