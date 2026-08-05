import asyncio
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import uuid4

import pytest
from websockets.exceptions import ConnectionClosed

from backend.data.binance_usdm import (
    BINANCE_USDM_FSTREAM_BASE_URL,
    BINANCE_USDM_PROVIDER,
    BinanceUsdMStreamingProvider,
    BookTicker,
    MarkPriceUpdate,
)
from backend.data.models import Instrument


class FakeWebSocket:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self._messages = messages
        self.closed = False

    def __aiter__(self) -> AsyncIterator[str]:
        async def messages() -> AsyncIterator[str]:
            for message in self._messages:
                yield json.dumps(message)

        return messages()

    async def close(self) -> None:
        self.closed = True


class ClosingWebSocket(FakeWebSocket):
    def __aiter__(self) -> AsyncIterator[str]:
        async def messages() -> AsyncIterator[str]:
            yield json.dumps(self._messages[0])
            raise ConnectionClosed(None, None)

        return messages()


class FakeConnection:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> FakeWebSocket:
        return self.websocket

    async def __aexit__(self, *_args: object) -> None:
        await self.websocket.close()


@pytest.fixture
def instrument() -> Instrument:
    return Instrument(uuid4(), "BTCUSDT", BINANCE_USDM_PROVIDER, "crypto_futures")


def kline(closed: bool, open_time: int = 1_000) -> dict[str, object]:
    return {
        "e": "kline",
        "k": {
            "t": open_time,
            "T": open_time + 59_999,
            "o": "100",
            "h": "101",
            "l": "99",
            "c": "100.5",
            "v": "2",
            "q": "200",
            "n": 2,
            "V": "1",
            "Q": "100",
            "x": closed,
        },
    }


@pytest.mark.asyncio
async def test_candles_gate_incomplete_and_deduplicate_final_messages(
    instrument: Instrument,
) -> None:
    fake = FakeWebSocket([kline(False), kline(True), kline(True)])
    provider = BinanceUsdMStreamingProvider(
        connection_factory=lambda _url, **_kwargs: FakeConnection(fake),
    )

    candles = [candle async for candle in provider.subscribe_candles(instrument, "1m")]

    assert len(candles) == 1
    assert candles[0].is_complete
    assert candles[0].close == Decimal("100.5")


@pytest.mark.asyncio
async def test_completed_candle_deduplication_survives_reconnect(
    instrument: Instrument,
) -> None:
    sockets = [ClosingWebSocket([kline(True)]), FakeWebSocket([kline(True)])]
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)

    def factory(_url: str, **_kwargs: object) -> FakeConnection:
        return FakeConnection(sockets.pop(0))

    provider = BinanceUsdMStreamingProvider(
        connection_factory=factory,
        sleeper=sleeper,
        max_reconnect_attempts=1,
    )

    candles = [candle async for candle in provider.subscribe_candles(instrument, "1m")]

    assert len(candles) == 1
    assert sleeps == [1.0]


@pytest.mark.asyncio
async def test_stream_selection_and_url_are_provider_specific(instrument: Instrument) -> None:
    urls: list[str] = []
    sockets = {
        "book": FakeWebSocket(
            [{"e": "bookTicker", "E": 1_000, "b": "100", "a": "101"}]
        ),
        "mark": FakeWebSocket(
            [
                {
                    "e": "markPriceUpdate",
                    "E": 1_000,
                    "p": "100",
                    "i": "99",
                    "r": "0",
                    "T": 2_000,
                }
            ]
        ),
    }

    def factory(url: str, **_kwargs: object) -> FakeConnection:
        urls.append(url)
        return FakeConnection(sockets["book" if "bookTicker" in url else "mark"])

    provider = BinanceUsdMStreamingProvider(connection_factory=factory)
    book = [value async for value in provider.subscribe_book_tickers(instrument)]
    mark = [value async for value in provider.subscribe_mark_prices(instrument)]

    assert isinstance(book[0], BookTicker)
    assert isinstance(mark[0], MarkPriceUpdate)
    assert urls == [
        f"{BINANCE_USDM_FSTREAM_BASE_URL}/btcusdt@bookTicker",
        f"{BINANCE_USDM_FSTREAM_BASE_URL}/btcusdt@markPrice@1s",
    ]


@pytest.mark.asyncio
async def test_duplicate_active_subscription_is_rejected_and_cleanup_releases_key(
    instrument: Instrument,
) -> None:
    gate = asyncio.Event()
    class WaitingSocket(FakeWebSocket):
        def __aiter__(self) -> AsyncIterator[str]:
            async def wait_forever() -> AsyncIterator[str]:
                await gate.wait()
                if False:
                    yield "{}"

            return wait_forever()

    waiting = WaitingSocket([])
    provider = BinanceUsdMStreamingProvider(
        connection_factory=lambda _url, **_kwargs: FakeConnection(waiting),
    )
    first = provider.subscribe_ticks(instrument)
    task = asyncio.create_task(first.__anext__())
    await asyncio.sleep(0)
    duplicate = provider.subscribe_ticks(instrument)

    with pytest.raises(ValueError, match="duplicate active"):
        await duplicate.__anext__()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await first.aclose()

    # Cancellation must release the logical key.
    gate.set()
    assert [value async for value in provider.subscribe_ticks(instrument)] == []
