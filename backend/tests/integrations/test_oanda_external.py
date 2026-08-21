"""Opt-in, historical-only OANDA Practice smoke validation."""

import os
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from backend.integrations.oanda import OandaHistoricalBarSource


def _external_range() -> tuple[datetime, datetime] | None:
    start_text = os.environ.get("ATLAS_EXTERNAL_OANDA_START")
    end_text = os.environ.get("ATLAS_EXTERNAL_OANDA_END")
    if not start_text or not end_text:
        return None
    try:
        start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if (
        start.tzinfo is None
        or start.utcoffset() != timedelta(0)
        or end.tzinfo is None
        or end.utcoffset() != timedelta(0)
        or start.second
        or start.microsecond
        or end.second
        or end.microsecond
        or end <= start
        or end - start > timedelta(hours=4)
        or end > datetime.now(UTC) - timedelta(minutes=2)
    ):
        return None
    return start.astimezone(UTC), end.astimezone(UTC)


@pytest.mark.external
def test_oanda_practice_historical_smoke() -> None:
    token = os.environ.get("ATLAS_EXTERNAL_OANDA_TOKEN")
    requested = _external_range()
    if not token or requested is None:
        pytest.skip(
            "set ATLAS_EXTERNAL_OANDA_TOKEN, ATLAS_EXTERNAL_OANDA_START, "
            "and ATLAS_EXTERNAL_OANDA_END to run the opt-in smoke test"
        )
    result = OandaHistoricalBarSource(SecretStr(token)).fetch(*requested)
    assert result.bars or result.incomplete
    assert all(bar.instrument.value == "EUR/USD" for bar in result.bars)
    assert all(bar.timeframe.value == "1m" for bar in result.bars)
