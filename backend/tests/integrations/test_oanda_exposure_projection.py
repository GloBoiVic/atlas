from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

import pytest

from backend.domain.market_data import Provider
from backend.domain.trading import FinancialPositionState
from backend.integrations.oanda import (
    OandaExposureProjectionError,
    OandaPracticeAccountIdentity,
    OandaPracticeOpenPosition,
    OandaPracticeOpenPositionInventory,
    OandaPracticeOpenTrade,
    OandaPracticeOpenTradeInventory,
    OandaPracticePositionSide,
    normalize_oanda_practice_account_position_inventory,
    project_oanda_practice_eur_usd_exposure_state,
)

ACCOUNT_ID = "001-011-5838423-001"


def account_identity() -> OandaPracticeAccountIdentity:
    return OandaPracticeAccountIdentity(
        provider=Provider.OANDA,
        environment="PRACTICE",
        provider_account_id=ACCOUNT_ID,
        alias="Research Practice",
        base_currency="USD",
    )


def trade(
    units: str = "100",
    *,
    trade_id: str = "1",
    instrument: str = "EUR_USD",
    state: Literal["OPEN", "CLOSE_WHEN_TRADEABLE"] = "OPEN",
) -> OandaPracticeOpenTrade:
    return OandaPracticeOpenTrade(
        provider_trade_id=trade_id,
        provider_instrument=instrument,
        open_time=datetime(2026, 1, 5, 10, tzinfo=UTC),
        open_price=Decimal("1.1000"),
        current_units=Decimal(units),
        state=state,
        unrealized_pl=Decimal("2.50"),
    )


def position(
    long_units: str = "100",
    short_units: str = "0",
    *,
    instrument: str = "EUR_USD",
) -> OandaPracticeOpenPosition:
    return OandaPracticeOpenPosition(
        provider_instrument=instrument,
        unrealized_pl=Decimal("2.50"),
        long=OandaPracticePositionSide(
            units=Decimal(long_units),
            average_price=Decimal("1.1000"),
            unrealized_pl=Decimal("3.00"),
        ),
        short=OandaPracticePositionSide(
            units=Decimal(short_units),
            average_price=Decimal("1.2000"),
            unrealized_pl=Decimal("-0.50"),
        ),
    )


def observations(
    *,
    trades: tuple[OandaPracticeOpenTrade, ...] = (),
    positions: tuple[OandaPracticeOpenPosition, ...] = (),
    trade_identity: OandaPracticeAccountIdentity | None = None,
    position_identity: OandaPracticeAccountIdentity | None = None,
    trade_transaction_id: str = "10",
    position_transaction_id: str = "20",
) -> tuple[OandaPracticeOpenTradeInventory, OandaPracticeOpenPositionInventory]:
    identity = account_identity()
    return (
        OandaPracticeOpenTradeInventory(
            identity=trade_identity or identity,
            trades=trades,
            last_transaction_id=trade_transaction_id,
        ),
        OandaPracticeOpenPositionInventory(
            identity=position_identity or identity,
            positions=positions,
            last_transaction_id=position_transaction_id,
        ),
    )


def account_position_payload(long_units: str, short_units: str) -> dict[str, Any]:
    return {
        "instrument": "EUR_USD",
        "unrealizedPL": "0",
        "long": {
            "units": long_units,
            "averagePrice": "1.1000",
            "unrealizedPL": "0",
        },
        "short": {
            "units": short_units,
            "averagePrice": "1.1000",
            "unrealizedPL": "0",
        },
    }


def test_matching_empty_inventories_project_flat() -> None:
    trades, positions = observations()

    assert project_oanda_practice_eur_usd_exposure_state(trades, positions) == (
        FinancialPositionState.FLAT
    )


@pytest.mark.parametrize(
    ("trade_items", "position_items"),
    [((trade(),), ()), ((), (position(),))],
)
def test_exposure_without_counterpart_fails_closed(
    trade_items: tuple[OandaPracticeOpenTrade, ...],
    position_items: tuple[OandaPracticeOpenPosition, ...],
) -> None:
    trades, positions = observations(trades=trade_items, positions=position_items)

    with pytest.raises(OandaExposureProjectionError):
        project_oanda_practice_eur_usd_exposure_state(trades, positions)


@pytest.mark.parametrize(
    ("trade_items", "position_items", "expected"),
    [
        ((trade("100"),), (position("100", "0"),), FinancialPositionState.LONG),
        (
            (trade("60"), trade("40", trade_id="2")),
            (position("100", "0"),),
            FinancialPositionState.LONG,
        ),
        ((trade("-100"),), (position("0", "-100"),), FinancialPositionState.SHORT),
        (
            (trade("-60"), trade("-40", trade_id="2")),
            (position("0", "-100"),),
            FinancialPositionState.SHORT,
        ),
    ],
)
def test_matching_trade_and_position_exposure_projects_state(
    trade_items: tuple[OandaPracticeOpenTrade, ...],
    position_items: tuple[OandaPracticeOpenPosition, ...],
    expected: FinancialPositionState,
) -> None:
    trades, positions = observations(trades=trade_items, positions=position_items)

    assert project_oanda_practice_eur_usd_exposure_state(trades, positions) == expected


def test_close_when_tradeable_trade_still_counts_as_long_exposure() -> None:
    trades, positions = observations(
        trades=(trade(state="CLOSE_WHEN_TRADEABLE"),),
        positions=(position(),),
    )

    assert project_oanda_practice_eur_usd_exposure_state(trades, positions) == (
        FinancialPositionState.LONG
    )


def test_opposing_trades_are_not_netted() -> None:
    trades, positions = observations(
        trades=(trade("100"), trade("-40", trade_id="2")),
        positions=(position("60", "0"),),
    )

    with pytest.raises(OandaExposureProjectionError):
        project_oanda_practice_eur_usd_exposure_state(trades, positions)


def test_dual_sided_position_is_not_netted() -> None:
    derived = normalize_oanda_practice_account_position_inventory(
        {
            "positions": [account_position_payload("100", "-40")],
            "lastTransactionID": "10",
        },
        account_identity(),
    )
    trades, positions = observations(
        trades=(trade("100"),), positions=derived.positions
    )

    with pytest.raises(OandaExposureProjectionError):
        project_oanda_practice_eur_usd_exposure_state(trades, positions)


def test_projection_receives_no_exposure_from_historical_account_position() -> None:
    derived = normalize_oanda_practice_account_position_inventory(
        {
            "positions": [
                {
                    "instrument": "EUR_USD",
                    "long": {"units": "0"},
                    "short": {"units": "-0"},
                }
            ],
            "lastTransactionID": "10",
        },
        account_identity(),
    )
    trades, positions = observations(positions=derived.positions)

    assert project_oanda_practice_eur_usd_exposure_state(trades, positions) == (
        FinancialPositionState.FLAT
    )


@pytest.mark.parametrize(
    ("trade_items", "position_items"),
    [
        ((trade("100"),), (position("99", "0"),)),
        ((trade("-100"),), (position("0", "-99"),)),
        ((trade("100"),), (position("0", "-100"),)),
        ((trade("-100"),), (position("100", "0"),)),
    ],
)
def test_direction_or_exact_unit_disagreement_fails_closed(
    trade_items: tuple[OandaPracticeOpenTrade, ...],
    position_items: tuple[OandaPracticeOpenPosition, ...],
) -> None:
    trades, positions = observations(trades=trade_items, positions=position_items)

    with pytest.raises(OandaExposureProjectionError):
        project_oanda_practice_eur_usd_exposure_state(trades, positions)


@pytest.mark.parametrize("unsupported", ["USD_CAD", "XAU_USD"])
def test_unsupported_trade_instrument_fails_closed(unsupported: str) -> None:
    trades, positions = observations(
        trades=(trade(instrument=unsupported),),
        positions=(position(),),
    )

    with pytest.raises(OandaExposureProjectionError):
        project_oanda_practice_eur_usd_exposure_state(trades, positions)


@pytest.mark.parametrize("unsupported", ["USD_CAD", "XAU_USD"])
def test_unsupported_position_instrument_fails_closed(unsupported: str) -> None:
    trades, positions = observations(
        trades=(trade(),),
        positions=(position(instrument=unsupported),),
    )

    with pytest.raises(OandaExposureProjectionError):
        project_oanda_practice_eur_usd_exposure_state(trades, positions)


def test_financial_identity_must_match_but_alias_differences_are_ignored() -> None:
    alias_only = replace(account_identity(), alias="Renamed Practice")
    trades, positions = observations(
        trades=(trade(),),
        positions=(position(),),
        position_identity=alias_only,
    )
    assert project_oanda_practice_eur_usd_exposure_state(trades, positions) == (
        FinancialPositionState.LONG
    )

    mismatched_account = replace(
        account_identity(), provider_account_id="001-011-5838423-002"
    )
    trades, positions = observations(
        trades=(trade(),),
        positions=(position(),),
        position_identity=mismatched_account,
    )
    with pytest.raises(OandaExposureProjectionError):
        project_oanda_practice_eur_usd_exposure_state(trades, positions)


def test_transaction_ids_and_irrelevant_provider_fields_do_not_change_state() -> None:
    original_trade = trade()
    original_position = position()
    original_trades, original_positions = observations(
        trades=(original_trade,),
        positions=(original_position,),
    )
    changed_trade = replace(
        original_trade,
        provider_trade_id="99",
        open_time=datetime(2027, 2, 6, 11, tzinfo=UTC),
        open_price=Decimal("9.9999"),
        unrealized_pl=Decimal("-500.00"),
        state="CLOSE_WHEN_TRADEABLE",
    )
    changed_position = replace(
        original_position,
        unrealized_pl=Decimal("-600.00"),
        long=replace(
            original_position.long,
            average_price=Decimal("9.8888"),
            unrealized_pl=Decimal("-700.00"),
        ),
        short=replace(
            original_position.short,
            average_price=Decimal("8.7777"),
            unrealized_pl=Decimal("-800.00"),
        ),
    )
    changed_trades, changed_positions = observations(
        trades=(changed_trade,),
        positions=(changed_position,),
        trade_identity=replace(account_identity(), alias="Another alias"),
        trade_transaction_id="101",
        position_transaction_id="202",
    )

    assert (
        project_oanda_practice_eur_usd_exposure_state(
            original_trades, original_positions
        )
        == project_oanda_practice_eur_usd_exposure_state(
            changed_trades, changed_positions
        )
        == FinancialPositionState.LONG
    )


def test_projection_is_deterministic_and_does_not_mutate_inventories() -> None:
    trades, positions = observations(
        trades=(trade("60"), trade("40", trade_id="2")),
        positions=(position(),),
        trade_transaction_id="301",
        position_transaction_id="302",
    )
    before_trades = trades
    before_positions = positions

    first = project_oanda_practice_eur_usd_exposure_state(trades, positions)
    second = project_oanda_practice_eur_usd_exposure_state(trades, positions)

    assert first is second is FinancialPositionState.LONG
    assert trades == before_trades
    assert positions == before_positions
