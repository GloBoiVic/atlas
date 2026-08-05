from pathlib import Path

import pytest

from backend.data import (
    BINANCE_USDM_PROVIDER,
    BinanceUsdMStreamingProvider,
    DuplicateLiveProviderError,
    LiveDataProvider,
    LiveProviderRegistry,
    UnknownLiveProviderError,
    create_live_provider_registry,
)


class StubLiveProvider(LiveDataProvider):
    def subscribe_candles(self, instrument, timeframe):
        raise NotImplementedError

    def subscribe_ticks(self, instrument):
        raise NotImplementedError


def test_live_registry_creates_provider_from_named_factory() -> None:
    provider = StubLiveProvider()
    registry = LiveProviderRegistry({"stub": lambda: provider})

    assert registry.get_factory("stub")() is provider
    assert registry.get_provider("stub") is provider


def test_live_registry_rejects_duplicate_registration_deterministically() -> None:
    registry = LiveProviderRegistry()
    registry.register("stub", StubLiveProvider)

    with pytest.raises(DuplicateLiveProviderError, match="stub"):
        registry.register("stub", StubLiveProvider)


def test_live_registry_rejects_unknown_provider_deterministically() -> None:
    with pytest.raises(UnknownLiveProviderError, match="missing"):
        LiveProviderRegistry().create("missing")


def test_builtin_registry_uses_usdm_identity_and_isolates_provider_instances() -> None:
    registry = create_live_provider_registry()

    first = registry.create(BINANCE_USDM_PROVIDER)
    second = registry.create(BINANCE_USDM_PROVIDER)

    assert isinstance(first, BinanceUsdMStreamingProvider)
    assert isinstance(second, BinanceUsdMStreamingProvider)
    assert first is not second
    assert first._active_subscriptions is not second._active_subscriptions
    assert first._emitted_candles is not second._emitted_candles


def test_builtin_registry_does_not_construct_transport_at_registration() -> None:
    calls = 0

    def connection_factory(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("transport must not be constructed during registration")

    registry = create_live_provider_registry(connection_factory=connection_factory)
    assert calls == 0
    registry.create(BINANCE_USDM_PROVIDER)
    assert calls == 0


def test_live_registry_is_separate_from_historical_registry(tmp_path: Path) -> None:
    from backend.data import create_historical_provider_registry

    historical = create_historical_provider_registry(data_dir=tmp_path)
    live = create_live_provider_registry()

    assert historical.get("binance").__class__.__name__ == "BinanceHistoricalProvider"
    with pytest.raises(UnknownLiveProviderError):
        live.create("binance")
