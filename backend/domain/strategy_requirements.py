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


def requirement_for_version(version) -> StrategyMarketDataRequirement:
    """Derive the canonical requirement from a StrategyVersion domain object.

    ``version`` is expected to expose ``id``, ``primary_timeframe``,
    and ``warm_up_bars``.  This keeps the historical loader decoupled from
    EMA/ATR internals — it only consumes this value object.
    """
    warm_up = int(getattr(version, "warm_up_bars", 0))
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
        context=RequiredHistoricalContext(analytical_bars=warm_up),
    )
