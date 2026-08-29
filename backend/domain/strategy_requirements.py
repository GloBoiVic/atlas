"""Canonical Strategy Market Data Requirements — Strategy-owned."""

from dataclasses import dataclass

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    Instrument,
    PriceComponent,
    Timeframe,
)


@dataclass(frozen=True, slots=True)
class AnalyticalRequirement:
    """What bars the Strategy evaluates — Strategy-owned."""

    instrument: Instrument = Instrument.EUR_USD
    resolution: Timeframe = Timeframe.M15
    price_component: PriceComponent = PriceComponent.MID
    alignment_convention: str = ALIGNMENT_CONVENTION
    completed_only: bool = True


@dataclass(frozen=True, slots=True)
class RequiredHistoricalContext:
    """How many eligible completed analytical bars before trading_start.

    Replaces treating ``warm_up_bars=100`` as an Atlas-global rule.
    The loader counts *eligible* completed M15 bars ending ``<= trading_start``,
    never wall-clock minutes.  Values:
      * 0 = pure price-action needing no prior context
      * 1-2 = price-action needing 1-2 prior bars
      * 100 = EMA100 / ATR14 state
      * 200 = EMA200 conservative maximum for v2 (this recovery)
    The loader never imports indicator logic; it only reads this value.
    """

    analytical_bars: int

    def __post_init__(self) -> None:
        if type(self.analytical_bars) is not int or self.analytical_bars < 0:
            raise ValueError("analytical_bars must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class StrategyMarketDataRequirement:
    """Authoritative market-data requirement for one StrategyVersion."""

    strategy_version_id: str
    analytical: AnalyticalRequirement
    context: RequiredHistoricalContext
    execution_components: tuple[PriceComponent, ...] = (
        PriceComponent.BID,
        PriceComponent.ASK,
    )

    @property
    def required_historical_context_bars(self) -> int:
        """The canonical warm-history requirement exposed to loaders."""
        return self.context.analytical_bars

    def __post_init__(self) -> None:
        if type(self.strategy_version_id) is not str or not self.strategy_version_id:
            raise ValueError("strategy_version_id must be a non-empty string")
        if (
            type(self.execution_components) is not tuple
            or self.execution_components
            != (
                PriceComponent.BID,
                PriceComponent.ASK,
            )
        ):
            raise ValueError("execution_components must be BID and ASK")


def requirement_for_version(version) -> StrategyMarketDataRequirement:
    """Derive the canonical requirement from a StrategyVersion domain object.

    ``version`` is expected to expose ``id``, ``primary_timeframe``,
    and ``required_historical_context_bars``. A transitional warm-up read is
    accepted only at this boundary for rows created before the contract change.
    This keeps the historical loader decoupled from
    EMA/ATR internals — it only consumes this value object.
    """
    context_bars = getattr(version, "required_historical_context_bars", None)
    if context_bars is None:
        # Read-only compatibility for pre-canonical persisted versions. New
        # production versions expose required_historical_context_bars.
        context_bars = getattr(version, "warm_up_bars", 0)
    timeframe = getattr(version, "primary_timeframe", Timeframe.M15)
    # Normalize string timeframe to enum when coming from persistence
    if isinstance(timeframe, str):
        timeframe = Timeframe(timeframe)
    return StrategyMarketDataRequirement(
        strategy_version_id=str(getattr(version, "id", "")),
        analytical=AnalyticalRequirement(
            resolution=timeframe,
            price_component=PriceComponent.MID,
        ),
        context=RequiredHistoricalContext(analytical_bars=int(context_bars)),
    )
