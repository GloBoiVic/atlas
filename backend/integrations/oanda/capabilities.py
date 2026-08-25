"""Small explicit OANDA provider capability contract — no plugin framework."""

from dataclasses import dataclass

from backend.domain.market_data import Instrument, PriceComponent, Provider, Timeframe

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


# Singleton instance for the current venue
OANDA_CAPABILITY = ProviderCapability()
