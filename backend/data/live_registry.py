"""Composition and lookup for live market-data providers.

The live registry is intentionally separate from the historical registry.  It stores
factories rather than provider instances so each feed session can receive an isolated
provider with its own subscriptions and deduplication state.
"""

from collections.abc import Callable, Mapping

from backend.data.binance_usdm import BinanceUsdMStreamingConfig, BinanceUsdMStreamingProvider
from backend.data.binance_usdm_stream import ConnectionFactory, ErrorPublisher, Sleeper
from backend.data.interfaces import LiveDataProvider

type LiveProviderFactory = Callable[[], LiveDataProvider]


class UnknownLiveProviderError(ValueError):
    """Raised when a live provider name is not registered."""


class DuplicateLiveProviderError(ValueError):
    """Raised when a live provider name is registered more than once."""


class LiveProviderRegistry:
    """Store side-effect-free live provider factories behind explicit names."""

    def __init__(self, providers: Mapping[str, LiveProviderFactory] | None = None) -> None:
        self._factories: dict[str, LiveProviderFactory] = {}
        for name, factory in (providers or {}).items():
            self.register(name, factory)

    def register(self, name: str, factory: LiveProviderFactory) -> None:
        """Register *factory* under *name*, rejecting duplicate names."""
        if name in self._factories:
            raise DuplicateLiveProviderError(f"live provider already registered: {name}")
        self._factories[name] = factory

    def get_factory(self, name: str) -> LiveProviderFactory:
        """Return the factory registered under *name*.

        Raises:
            UnknownLiveProviderError: If *name* is not registered.
        """
        try:
            return self._factories[name]
        except KeyError:
            raise UnknownLiveProviderError(f"unknown live provider: {name}") from None

    def create(self, name: str) -> LiveDataProvider:
        """Create a new provider instance for *name*."""
        return self.get_factory(name)()

    def get_provider(self, name: str) -> LiveDataProvider:
        """Create a provider using the descriptive lookup name."""
        return self.create(name)


def create_live_provider_registry(
    *,
    config: BinanceUsdMStreamingConfig | None = None,
    connection_factory: ConnectionFactory | None = None,
    sleeper: Sleeper | None = None,
    error_publisher: ErrorPublisher | None = None,
) -> LiveProviderRegistry:
    """Compose the built-in public live providers without opening a connection.

    Transport construction is deferred until a caller creates a provider and starts a
    subscription.  A new provider is created for every lookup to preserve per-session
    subscription and candle-deduplication state.
    """

    def create_binance_usdm() -> LiveDataProvider:
        return BinanceUsdMStreamingProvider(
            config=config,
            connection_factory=connection_factory,
            sleeper=sleeper,
            error_publisher=error_publisher,
        )

    return LiveProviderRegistry({"binance_usdm": create_binance_usdm})


build_live_provider_registry = create_live_provider_registry
