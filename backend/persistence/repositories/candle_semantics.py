"""Shared validation for deterministic candle reads."""

from datetime import UTC, datetime
from uuid import UUID


def validate_candle_query(
    instrument_id: UUID,
    timeframe: str,
    start: datetime,
    end: datetime,
    price_basis: str,
) -> None:
    """Validate the common CandleRepository query boundary."""
    if not isinstance(instrument_id, UUID):
        raise TypeError("instrument_id must be a UUID")
    if not timeframe:
        raise ValueError("timeframe must not be empty")
    if not price_basis:
        raise ValueError("price_basis must not be empty")
    for value, name in ((start, "start"), (end, "end")):
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError(f"{name} must be UTC")
    if end < start:
        raise ValueError("end must not be before start")
