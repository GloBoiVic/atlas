"""CSV historical market-data provider.

The CSV contract is deliberately small and explicit: files are UTF-8 CSV files named
``<symbol>.csv`` under ``data_dir``.  They must contain the columns
``timestamp,open,high,low,close,base_volume``.  Optional columns are
``close_time,quote_volume,trade_count,taker_buy_base_volume,taker_buy_quote_volume``.
``tick_volume`` is intentionally excluded because it is an OANDA price-update metric,
not CSV trade volume; OANDA support is deferred.
Timestamps must be timezone-aware ISO-8601 values; naive timestamps are rejected.
Duplicate timestamps are allowed only when their complete normalized rows are identical.
"""

import asyncio
import csv
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from backend.data.interfaces import HistoricalDataProvider
from backend.data.models import Candle, Instrument

_REQUIRED_COLUMNS = frozenset({"timestamp", "open", "high", "low", "close", "base_volume"})
_OPTIONAL_COLUMNS = frozenset(
    {
        "close_time",
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    }
)


class CSVDataProvider(HistoricalDataProvider):
    """Load validated historical candles from a bounded CSV file."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir).resolve()

    async def get_historical_candles(
        self,
        instrument: Instrument,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Read and normalize candles without blocking the event loop.

        Args:
            instrument: Resolved CSV instrument.
            timeframe: Candle timeframe label.
            start: Inclusive UTC range start.
            end: Inclusive UTC range end.

        Returns:
            Deterministically sorted, deduplicated candles in the requested range.

        Raises:
            ValueError: If the request or CSV violates the fixture contract.
            FileNotFoundError: If the symbol file does not exist.
            asyncio.CancelledError: If the caller cancels the operation.
        """
        _validate_request(instrument, timeframe, start, end)
        path = self._path_for_symbol(instrument.symbol)
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            None,
            self._parse_file,
            path,
            instrument,
            timeframe,
            _utc(start),
            _utc(end),
        )
        try:
            return await future
        except asyncio.CancelledError:
            # Cancelling the future prevents delivery of a result.  The parser owns its
            # file context, so it closes the file when the worker thread unwinds.
            future.cancel()
            raise

    def _path_for_symbol(self, symbol: str) -> Path:
        if not symbol or Path(symbol).name != symbol or symbol in {".", ".."}:
            raise ValueError("instrument symbol must be a simple CSV filename stem")
        path = (self.data_dir / f"{symbol}.csv").resolve()
        if self.data_dir not in path.parents:
            raise ValueError("CSV path escapes data directory")
        return path

    @staticmethod
    def _parse_file(
        path: Path,
        instrument: Instrument,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        candles_by_time: dict[datetime, Candle] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            fieldnames = frozenset(reader.fieldnames or ())
            missing = _REQUIRED_COLUMNS - fieldnames
            unknown = fieldnames - _REQUIRED_COLUMNS - _OPTIONAL_COLUMNS
            if missing:
                raise ValueError(f"CSV missing required columns: {sorted(missing)}")
            if unknown:
                raise ValueError(f"CSV contains unsupported columns: {sorted(unknown)}")

            for row_number, row in enumerate(reader, start=2):
                candle = _parse_row(row, row_number, instrument, timeframe)
                if start <= candle.open_time <= end:
                    previous = candles_by_time.get(candle.open_time)
                    if previous is not None and previous != candle:
                        raise ValueError(f"conflicting duplicate timestamp at row {row_number}")
                    candles_by_time[candle.open_time] = candle
        return [candles_by_time[key] for key in sorted(candles_by_time)]


def _parse_row(
    row: dict[str, str | None],
    row_number: int,
    instrument: Instrument,
    timeframe: str,
) -> Candle:
    try:
        open_time = _parse_timestamp(_required(row, "timestamp", row_number))
        values = {
            "open": _decimal(row, "open", row_number),
            "high": _decimal(row, "high", row_number),
            "low": _decimal(row, "low", row_number),
            "close": _decimal(row, "close", row_number),
            "base_volume": _decimal(row, "base_volume", row_number),
        }
        close_time = _optional_timestamp(row.get("close_time"), row_number, "close_time")
        quote_volume = _optional_decimal(row.get("quote_volume"), row_number, "quote_volume")
        trade_count = _optional_int(row.get("trade_count"), row_number, "trade_count")
        taker_base = _optional_decimal(
            row.get("taker_buy_base_volume"), row_number, "taker_buy_base_volume"
        )
        taker_quote = _optional_decimal(
            row.get("taker_buy_quote_volume"), row_number, "taker_buy_quote_volume"
        )
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid CSV row {row_number}: {exc}") from exc

    if close_time is not None and close_time < open_time:
        raise ValueError(f"invalid CSV row {row_number}: close_time precedes timestamp")
    if values["low"] <= 0 or values["high"] <= 0:
        raise ValueError(f"invalid CSV row {row_number}: prices must be positive")
    if values["high"] < max(values["open"], values["close"]):
        raise ValueError(f"invalid CSV row {row_number}: high is below open or close")
    if values["low"] > min(values["open"], values["close"]):
        raise ValueError(f"invalid CSV row {row_number}: low is above open or close")
    if values["base_volume"] < 0 or (quote_volume is not None and quote_volume < 0):
        raise ValueError(f"invalid CSV row {row_number}: volume cannot be negative")
    if trade_count is not None and trade_count < 0:
        raise ValueError(f"invalid CSV row {row_number}: trade_count cannot be negative")

    return Candle(
        instrument_id=instrument.id,
        provider=instrument.provider,
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time,
        price_basis="trade",
        open=values["open"],
        high=values["high"],
        low=values["low"],
        close=values["close"],
        base_volume=values["base_volume"],
        quote_volume=quote_volume,
        trade_count=trade_count,
        taker_buy_base_volume=taker_base,
        taker_buy_quote_volume=taker_quote,
        is_complete=True,
    )


def _validate_request(
    instrument: Instrument, timeframe: str, start: datetime, end: datetime
) -> None:
    if instrument.provider != "csv":
        raise ValueError("CSVDataProvider requires an instrument with provider='csv'")
    if not timeframe:
        raise ValueError("timeframe must not be empty")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("historical range timestamps must be timezone-aware")
    if _utc(start) > _utc(end):
        raise ValueError("historical range start must not be after end")


def _required(row: dict[str, str | None], name: str, row_number: int) -> str:
    value = row.get(name)
    if value is None or not value.strip():
        raise ValueError(f"missing {name}")
    return value.strip()


def _decimal(row: dict[str, str | None], name: str, row_number: int) -> Decimal:
    return _finite_decimal(Decimal(_required(row, name, row_number)), name)


def _optional_decimal(value: str | None, row_number: int, name: str) -> Decimal | None:
    if value is None or not value.strip():
        return None
    return _finite_decimal(Decimal(value.strip()), name)


def _finite_decimal(value: Decimal, name: str) -> Decimal:
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _optional_int(value: str | None, row_number: int, name: str) -> int | None:
    return None if value is None or not value.strip() else int(value.strip())


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return _utc(parsed)


def _optional_timestamp(value: str | None, row_number: int, name: str) -> datetime | None:
    return None if value is None or not value.strip() else _parse_timestamp(value.strip())


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)
