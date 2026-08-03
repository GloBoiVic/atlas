from pathlib import Path

import pytest

from backend.data import (
    BinanceHistoricalProvider,
    CSVDataProvider,
    DuplicateHistoricalProviderError,
    HistoricalDataProvider,
    HistoricalProviderRegistry,
    UnknownHistoricalProviderError,
    create_historical_provider_registry,
)


class StubHistoricalProvider(HistoricalDataProvider):
    async def get_historical_candles(self, instrument, timeframe, start, end):
        return []


def test_registry_registers_and_looks_up_provider() -> None:
    provider = StubHistoricalProvider()
    registry = HistoricalProviderRegistry()

    registry.register("stub", provider)

    assert registry.get("stub") is provider
    assert registry.get_provider("stub") is provider


def test_registry_rejects_duplicate_registration() -> None:
    registry = HistoricalProviderRegistry()
    registry.register("stub", StubHistoricalProvider())

    with pytest.raises(DuplicateHistoricalProviderError):
        registry.register("stub", StubHistoricalProvider())


def test_registry_rejects_unknown_provider() -> None:
    with pytest.raises(UnknownHistoricalProviderError):
        HistoricalProviderRegistry().get("missing")


def test_factory_constructs_default_providers(tmp_path: Path) -> None:
    registry = create_historical_provider_registry(data_dir=tmp_path)

    assert isinstance(registry.get("csv"), CSVDataProvider)
    assert isinstance(registry.get("binance"), BinanceHistoricalProvider)
    assert registry.get("csv").data_dir == tmp_path.resolve()


def test_factory_injects_binance_exchange_factory(tmp_path: Path) -> None:
    exchange = object()

    def exchange_factory():
        return exchange

    registry = create_historical_provider_registry(
        data_dir=tmp_path,
        exchange_factory=exchange_factory,
    )

    provider = registry.get("binance")
    assert isinstance(provider, BinanceHistoricalProvider)
    assert provider._exchange_factory() is exchange


def test_factory_does_not_create_exchange_during_composition(tmp_path: Path) -> None:
    calls = 0

    def exchange_factory():
        nonlocal calls
        calls += 1
        raise AssertionError("exchange must not be created during composition")

    create_historical_provider_registry(
        data_dir=tmp_path,
        exchange_factory=exchange_factory,
    )

    assert calls == 0
