from dataclasses import replace
from decimal import Decimal

import pytest

from backend.domain.market_data import Provider
from backend.integrations.oanda import (
    OandaPracticeAccountIdentity,
    OandaPracticeAccountSummarySnapshot,
    project_oanda_practice_account_state,
)
from backend.risk import AccountState

ACCOUNT_ID = "001-011-5838423-001"


def account_identity(
    *, account_id: str = ACCOUNT_ID, alias: str | None = "Research Practice"
) -> OandaPracticeAccountIdentity:
    return OandaPracticeAccountIdentity(
        provider=Provider.OANDA,
        environment="PRACTICE",
        provider_account_id=account_id,
        alias=alias,
        base_currency="USD",
    )


def account_summary(
    *,
    nav: Decimal = Decimal("10000.00"),
    balance: Decimal = Decimal("12345.67"),
    unrealized_pl: Decimal = Decimal("-12.34"),
    margin_used: Decimal = Decimal("456.78"),
    margin_available: Decimal = Decimal("8765.43"),
    open_trade_count: int = 1,
    open_position_count: int = 2,
    pending_order_count: int = 3,
    last_transaction_id: str = "42",
    identity: OandaPracticeAccountIdentity | None = None,
) -> OandaPracticeAccountSummarySnapshot:
    return OandaPracticeAccountSummarySnapshot(
        identity=identity or account_identity(),
        balance=balance,
        nav=nav,
        unrealized_pl=unrealized_pl,
        margin_used=margin_used,
        margin_available=margin_available,
        open_trade_count=open_trade_count,
        open_position_count=open_position_count,
        pending_order_count=pending_order_count,
        last_transaction_id=last_transaction_id,
    )


def test_projection_maps_currency_and_nav_exactly() -> None:
    summary = account_summary(
        balance=Decimal("20000.00"),
        nav=Decimal("10000.00"),
        margin_available=Decimal("30000.00"),
    )

    result = project_oanda_practice_account_state(summary)

    assert result == AccountState(base_currency="USD", equity=summary.nav)
    assert result.base_currency == summary.identity.base_currency
    assert result.equity == summary.nav


@pytest.mark.parametrize(
    "nav",
    [Decimal("10000.00"), Decimal("0"), Decimal("-25.50")],
)
def test_projection_preserves_positive_zero_and_negative_nav(nav: Decimal) -> None:
    summary = account_summary(nav=nav)

    result = project_oanda_practice_account_state(summary)

    assert result.equity == nav


def test_irrelevant_account_fields_do_not_change_projection() -> None:
    original = account_summary()
    changed = replace(
        original,
        identity=account_identity(
            account_id="001-011-5838423-002", alias="Different alias"
        ),
        balance=Decimal("-1.00"),
        unrealized_pl=Decimal("999.00"),
        margin_used=Decimal("800.00"),
        margin_available=Decimal("1.00"),
        open_trade_count=10,
        open_position_count=20,
        pending_order_count=30,
        last_transaction_id="43",
    )

    assert project_oanda_practice_account_state(original) == (
        project_oanda_practice_account_state(changed)
    )


def test_projection_does_not_mutate_source_and_is_deterministic() -> None:
    summary = account_summary(nav=Decimal("-25.50"))
    before = summary

    first = project_oanda_practice_account_state(summary)
    second = project_oanda_practice_account_state(summary)

    assert first == second
    assert summary == before
