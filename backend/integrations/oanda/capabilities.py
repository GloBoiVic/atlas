"""Small explicit OANDA provider capability contract — no plugin framework."""

from dataclasses import dataclass
from decimal import Decimal

from backend.domain.market_data import (
    InputError,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
)
from backend.domain.strategy import MarketSpecification

NATIVE_M15_CONTRACT = "OANDA_M15_NATIVE_UTC_V1"
NATIVE_M1_CONTRACT = "OANDA_M1_NATIVE_UTC_V1"


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    """What the provider can natively supply for EUR/USD."""

    provider: Provider = Provider.OANDA
    instrument: Instrument = Instrument.EUR_USD

    def supports(self, resolution: Timeframe, component: PriceComponent) -> bool:
        return (resolution, component) in {
            (Timeframe.M15, PriceComponent.MID),
            (Timeframe.M1, PriceComponent.BID),
            (Timeframe.M1, PriceComponent.ASK),
            (Timeframe.M1, PriceComponent.MID),
        }

    def native_contract(
        self, resolution: Timeframe, component: PriceComponent
    ) -> str | None:
        if (resolution, component) == (Timeframe.M15, PriceComponent.MID):
            return NATIVE_M15_CONTRACT
        if (resolution, component) in (
            (Timeframe.M1, PriceComponent.BID),
            (Timeframe.M1, PriceComponent.ASK),
            (Timeframe.M1, PriceComponent.MID),
        ):
            return NATIVE_M1_CONTRACT
        return None

    def analytical_contract(self) -> str:
        return NATIVE_M15_CONTRACT

    def execution_contracts(self) -> tuple[str, str]:
        return (NATIVE_M1_CONTRACT, NATIVE_M1_CONTRACT)

    def market_specification(
        self, instrument: Instrument = Instrument.EUR_USD
    ) -> MarketSpecification:
        """Return the only currently validated calculation capability."""
        if instrument is not self.instrument or self.provider is not Provider.OANDA:
            raise InputError("unsupported OANDA market capability")
        return MarketSpecification(instrument, Decimal("0.0001"))


# Singleton instance for the current venue
OANDA_CAPABILITY = ProviderCapability()


def validate_market_specification(specification: MarketSpecification) -> None:
    """Fail closed unless the explicit current capability owns the pip size."""
    if type(specification) is not MarketSpecification:
        raise InputError("market specification is invalid")
    expected = OANDA_CAPABILITY.market_specification(specification.instrument)
    if specification != expected:
        raise InputError("market specification does not match OANDA capability")
