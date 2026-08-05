"""Market-data provider interfaces.

``HistoricalDataProvider`` returns bounded lists of completed candles.
``LiveDataProvider`` is a stub interface — implementation is owned by Feature 08.
Both receive a resolved ``Instrument``, not a raw symbol string.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from datetime import datetime

from backend.data.models import Candle, Instrument, Tick


class HistoricalDataProvider(ABC):
    """Returns a bounded, sorted, deduplicated list of completed candles."""

    @abstractmethod
    async def get_historical_candles(
        self,
        instrument: Instrument,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Fetch historical candles for *instrument* within [*start*, *end*].

        Returns candles sorted by ``open_time``, with ``is_complete=True``,
        Decimal-normalised prices and volumes, and UTC timestamps.
        """


class LiveDataProvider(ABC):
    """Emits streaming candles and ticks.

    Implementation is owned by Feature 08.  Accepts a resolved ``Instrument``
    so that symbol resolution stays centralised.
    """

    @abstractmethod
    def subscribe_candles(
        self,
        instrument: Instrument,
        timeframe: str,
    ) -> AsyncGenerator[Candle, None]:
        """Yield completed candles as they stream in."""

    @abstractmethod
    def subscribe_ticks(
        self,
        instrument: Instrument,
    ) -> AsyncGenerator[Tick, None]:
        """Yield tick updates as they arrive."""
