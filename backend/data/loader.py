"""Historical data loading and reproducible dataset identity."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from backend.data.interfaces import HistoricalDataProvider
from backend.data.models import Candle, DatasetIdentity, HistoricalLoadResult, Instrument
from backend.persistence.repositories.protocols import CandleRepository, InstrumentRepository


class HistoricalDataLoader:
    """Resolve an instrument, load normalized candles, and persist them idempotently."""

    def __init__(
        self,
        provider: HistoricalDataProvider,
        instrument_repo: InstrumentRepository,
        candle_repo: CandleRepository,
    ) -> None:
        self.provider = provider
        self.instrument_repo = instrument_repo
        self.candle_repo = candle_repo

    async def load_historical_data(
        self,
        *,
        symbol: str,
        provider_name: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        asset_type: str = "crypto",
    ) -> HistoricalLoadResult:
        """Import one bounded historical dataset through repository boundaries."""
        if provider_name == "csv":
            # CSV carries no provider metadata.  Resolve only, preserving any existing
            # precision, currencies, and constraints supplied by an instrument owner.
            record = await self.instrument_repo.resolve(
                symbol=symbol,
                provider=provider_name,
                asset_type=asset_type,
            )
        else:
            # Metadata-bearing adapters (for example future Binance exchangeInfo) own
            # the explicit upsert path.
            record = await self.instrument_repo.upsert(
                symbol=symbol,
                provider=provider_name,
                asset_type=asset_type,
            )
        instrument = Instrument(
            id=record.id,
            symbol=record.symbol,
            provider=record.provider,
            asset_type=record.asset_type,
            base_currency=record.base_currency,
            quote_currency=record.quote_currency,
            price_precision=record.price_precision,
            quantity_precision=record.quantity_precision,
            is_active=record.is_active,
            constraints=record.constraints,
        )
        candles = await self.provider.get_historical_candles(instrument, timeframe, start, end)
        inserted_count = await self.candle_repo.save_many(candles)
        dataset = build_dataset_identity(
            instrument_id=instrument.id,
            timeframe=timeframe,
            start=start,
            end=end,
            source=provider_name,
            candles=candles,
        )
        return HistoricalLoadResult(dataset=dataset, inserted_count=inserted_count)


async def load_historical_data(
    *,
    provider: HistoricalDataProvider,
    instrument_repo: InstrumentRepository,
    candle_repo: CandleRepository,
    symbol: str,
    provider_name: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    asset_type: str = "crypto",
) -> HistoricalLoadResult:
    """Load historical data using the repository/provider composition contracts."""
    loader = HistoricalDataLoader(provider, instrument_repo, candle_repo)
    return await loader.load_historical_data(
        symbol=symbol,
        provider_name=provider_name,
        timeframe=timeframe,
        start=start,
        end=end,
        asset_type=asset_type,
    )


def build_dataset_identity(
    *,
    instrument_id: UUID,
    timeframe: str,
    start: datetime,
    end: datetime,
    source: str,
    candles: list[Candle],
) -> DatasetIdentity:
    """Build a SHA-256 identity from canonical metadata and normalized candle values."""
    canonical = {
        "instrument_id": str(instrument_id),
        "timeframe": timeframe,
        "start": _timestamp(start),
        "end": _timestamp(end),
        "source": source,
        "candles": [
            _canonical_candle(candle)
            for candle in sorted(candles, key=lambda item: item.open_time)
        ],
    }
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return DatasetIdentity(
        id=f"sha256:{fingerprint}",
        instrument_id=instrument_id,
        timeframe=timeframe,
        start=start.astimezone(UTC),
        end=end.astimezone(UTC),
        candle_count=len(candles),
        source=source,
    )


def _canonical_candle(candle: Candle) -> dict[str, object]:
    fields = (
        "instrument_id", "provider", "timeframe", "open_time", "close_time", "price_basis",
        "open", "high", "low", "close", "base_volume", "quote_volume", "trade_count",
        "taker_buy_base_volume", "taker_buy_quote_volume", "tick_volume", "is_complete",
    )
    return {
        field: _canonical_value(getattr(candle, field))
        for field in fields
    }


def _canonical_value(value: object) -> object:
    if isinstance(value, Decimal):
        normalized = value.normalize()
        return "0" if normalized == 0 else format(normalized, "f")
    if isinstance(value, datetime):
        return _timestamp(value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    return str(value)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("dataset timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
