import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from backend.domain.market_data import (
    Bar,
    InputError,
    Instrument,
    PriceComponent,
    Timeframe,
)
from backend.domain.strategy import MarketSpecification, StrategyContext

MARKET = MarketSpecification(Instrument.EUR_USD, Decimal("0.0001"))


def _bar() -> Bar:
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        Decimal("1.09"),
        Decimal("1.11"),
        Decimal("1.08"),
        Decimal("1.10"),
    )


def test_strategy_domain_has_no_oanda_capability_dependency() -> None:
    source_path = Path(__file__).parents[2] / "domain" / "strategy.py"
    tree = ast.parse(source_path.read_text())
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert all(
        node.module is None or "integrations.oanda" not in node.module
        for node in imports
    )
    assert "OANDA_CAPABILITY" not in source_path.read_text()


def test_context_requires_an_explicit_market_fact() -> None:
    with pytest.raises(InputError, match="market is missing"):
        StrategyContext(
            _bar().end_time,
            Instrument.EUR_USD,
            (_bar(),),
            market=cast(MarketSpecification, None),
        )


def test_provider_neutral_market_fact_composes_context() -> None:
    context = StrategyContext(
        _bar().end_time,
        Instrument.EUR_USD,
        (_bar(),),
        market=MARKET,
    )

    assert context.market is MARKET
    assert context.to_json()["market"] == {
        "instrument": "EUR/USD",
        "pip_size": "0.0001",
    }


def test_context_rejects_a_market_fact_for_another_instrument_shape() -> None:
    invalid_market = cast(MarketSpecification, object())
    with pytest.raises(InputError, match="market is missing or invalid"):
        StrategyContext(
            _bar().end_time,
            Instrument.EUR_USD,
            (_bar(),),
            market=invalid_market,
        )
