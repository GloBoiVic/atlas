from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.domain.market_data import PriceComponent, Timeframe
from backend.domain.strategy_requirements import requirement_for_version


def test_requirement_uses_canonical_context_and_sparse_execution() -> None:
    requirement = requirement_for_version(
        SimpleNamespace(
            id=uuid4(),
            primary_timeframe=Timeframe.M15,
            required_historical_context_bars=200,
        )
    )

    assert requirement.required_historical_context_bars == 200
    assert requirement.analytical.resolution is Timeframe.M15
    assert requirement.analytical.price_component is PriceComponent.MID
    assert requirement.execution_components == (
        PriceComponent.BID,
        PriceComponent.ASK,
    )


def test_requirement_rejects_noncanonical_execution_components() -> None:
    from backend.domain.strategy_requirements import (
        AnalyticalRequirement,
        RequiredHistoricalContext,
        StrategyMarketDataRequirement,
    )

    with pytest.raises(ValueError, match="execution_components"):
        StrategyMarketDataRequirement(
            str(uuid4()),
            AnalyticalRequirement(),
            RequiredHistoricalContext(0),
            (PriceComponent.MID,),
        )
