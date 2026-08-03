"""Composition and lookup for historical market-data providers."""

from collections.abc import Mapping
from pathlib import Path

from backend.data.binance_provider import BinanceHistoricalProvider, ExchangeFactory
from backend.data.csv_provider import CSVDataProvider
from backend.data.interfaces import HistoricalDataProvider


class UnknownHistoricalProviderError(ValueError):
    """Raised when a historical provider name is not registered."""


class DuplicateHistoricalProviderError(ValueError):
    """Raised when a provider name is registered more than once."""


class HistoricalProviderRegistry:
    """Store historical providers behind explicit provider names."""

    def __init__(
        self,
        providers: Mapping[str, HistoricalDataProvider] | None = None,
    ) -> None:
        self._providers: dict[str, HistoricalDataProvider] = {}
        for name, provider in (providers or {}).items():
            self.register(name, provider)

    def register(self, name: str, provider: HistoricalDataProvider) -> None:
        """Register *provider* under *name*, rejecting duplicate names."""
        if name in self._providers:
            raise DuplicateHistoricalProviderError(
                f"historical provider already registered: {name}"
            )
        self._providers[name] = provider

    def get(self, name: str) -> HistoricalDataProvider:
        """Return the provider registered under *name*.

        Raises:
            UnknownHistoricalProviderError: If *name* is not registered.
        """
        try:
            return self._providers[name]
        except KeyError:
            raise UnknownHistoricalProviderError(
                f"unknown historical provider: {name}"
            ) from None

    def get_provider(self, name: str) -> HistoricalDataProvider:
        """Return a registered provider using the descriptive lookup name."""
        return self.get(name)


def create_historical_provider_registry(
    *,
    data_dir: str | Path,
    exchange_factory: ExchangeFactory | None = None,
) -> HistoricalProviderRegistry:
    """Compose the built-in CSV and Binance historical providers.

    Provider construction is intentionally side-effect free.  In particular, the Binance
    exchange factory is retained by the provider and is not called until candles are fetched.
    """
    return HistoricalProviderRegistry(
        {
            "csv": CSVDataProvider(data_dir),
            "binance": BinanceHistoricalProvider(exchange_factory=exchange_factory),
        }
    )


build_historical_provider_registry = create_historical_provider_registry
