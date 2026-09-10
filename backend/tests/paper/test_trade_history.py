from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from backend.paper.trade_history import (
    PaperTradeHistoryReadError,
    PaperTradeHistoryReadService,
)

ATTEMPT_ID = UUID("12345678-1234-5678-1234-567812345678")
TRADE_ID = "7001"


class _Rows:
    def __init__(self, rows: Sequence[object]) -> None:
        self.rows = rows

    def all(self) -> Sequence[object]:
        return self.rows


class _Session:
    def __init__(
        self, rows: Sequence[object], transactions: Sequence[object] = ()
    ) -> None:
        self.rows = rows
        self.transactions = transactions
        self.execute_calls = 0
        self.scalar_calls = 0

    def execute(self, _: object) -> _Rows:
        self.execute_calls += 1
        return _Rows(self.rows)

    def scalars(self, _: object) -> _Rows:
        self.scalar_calls += 1
        return _Rows(self.transactions)


class _SqlLimitAwareSession(_Session):
    def __init__(
        self,
        rows: Sequence[object],
        *,
        sql_limit: int,
        transactions: Sequence[object] = (),
    ) -> None:
        super().__init__(rows, transactions)
        self.sql_limit = sql_limit

    def execute(self, _: object) -> _Rows:
        self.execute_calls += 1
        rows = self.rows
        if self.execute_calls == 1 and "LIMIT" in str(_).upper():
            rows = rows[: self.sql_limit]
        return _Rows(rows)


def _attempt(
    *,
    attempt_id: UUID = ATTEMPT_ID,
    trade_id: str | None = TRADE_ID,
    direction: str = "LONG",
    signed_units: Decimal | None = Decimal("19230"),
    entered_at: datetime | None = datetime(2026, 9, 2, 10, tzinfo=UTC),
    lifecycle: str = "LIFECYCLE_ADVANCED",
) -> SimpleNamespace:
    return SimpleNamespace(
        attempt_id=attempt_id,
        strategy_key="ema_sweep",
        strategy_version_number=3,
        instrument="EUR_USD",
        direction=direction,
        reconciliation_status=lifecycle,
        fill_broker_order_id="42" if trade_id else None,
        fill_transaction_id="43" if trade_id else None,
        fill_trade_id=trade_id,
        fill_signed_units=signed_units,
        fill_price=Decimal("1.10010") if trade_id else None,
        fill_executed_at=entered_at,
        fill_actual_initial_risk=Decimal("98.1150") if trade_id else None,
        stop_loss_status="CONFIRMED",
        stop_loss_price=Decimal("1.09500"),
        take_profit_status="CONFIRMED",
        take_profit_price=Decimal("1.11030"),
    )


def _strategy() -> SimpleNamespace:
    return SimpleNamespace(name="EMA Sweep Confirmation")


def _trade_observation(
    attempt_id: UUID = ATTEMPT_ID,
    *,
    close_time: str | None = "2026-09-02T14:00:00Z",
    trade_id: str = TRADE_ID,
    schema: str = "ATLAS_PAPER_BROKER_FACTS_V2",
    state: str = "CLOSED",
    closing_ids: list[str] | None = None,
    provider_trade_id: str | None = TRADE_ID,
) -> SimpleNamespace:
    facts: dict[str, object] = {
        "trade_id": trade_id,
        "state": state,
        "average_close_price": "1.11030",
        "realized_pl": "196.1538",
        "financing": "-0.42",
        "dividend_adjustment": "0",
        "closing_transaction_ids": closing_ids or ["43"],
    }
    if close_time is not None:
        facts["close_time"] = close_time
    return SimpleNamespace(
        attempt_id=attempt_id,
        normalized_schema_version=schema,
        read_kind="TRADE_DETAIL",
        object_kind="TRADE",
        provider_trade_id=provider_trade_id,
        normalized_facts=facts,
    )


def _transaction_observation(
    attempt_id: UUID = ATTEMPT_ID,
    *,
    transaction_id: str = "43",
    trade_id: str = TRADE_ID,
    cause: str = "TAKE_PROFIT",
    provider_transaction_id: str | None = "43",
    provider_trade_id: str | None = TRADE_ID,
    schema: str = "ATLAS_PAPER_BROKER_FACTS_V2",
) -> SimpleNamespace:
    return SimpleNamespace(
        attempt_id=attempt_id,
        normalized_schema_version=schema,
        read_kind="TRANSACTION_DETAIL",
        object_kind="TRANSACTION",
        provider_transaction_id=provider_transaction_id,
        provider_trade_id=provider_trade_id,
        normalized_facts={
            "transaction_id": transaction_id,
            "closed_trade_id": trade_id,
            "closed_units": "19230",
            "close_price": "1.11035",
            "close_realized_pl": "196.1538",
            "close_financing": "-0.42",
            "provider_reason": "TAKE_PROFIT_ORDER",
            "exit_cause": cause,
        },
    )


def _row(
    *,
    attempt: SimpleNamespace | None = None,
    observation: SimpleNamespace | None = None,
) -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    return (attempt or _attempt(), _strategy(), observation or _trade_observation())


def test_history_returns_empty_when_no_trade_is_eligible() -> None:
    session = _Session([])

    assert PaperTradeHistoryReadService().list(cast(Session, session)) == ()
    assert session.scalar_calls == 0


def test_history_composes_fill_closure_strategy_and_exact_cause() -> None:
    session = _Session(
        [_row()],
        [_transaction_observation()],
    )

    items = PaperTradeHistoryReadService().list(cast(Session, session))

    assert len(items) == 1
    assert items[0].to_json() == {
        "strategy_key": "ema_sweep",
        "strategy_name": "EMA Sweep Confirmation",
        "strategy_version_number": 3,
        "instrument": "EUR_USD",
        "direction": "LONG",
        "units": "19230",
        "entry_price": "1.10010",
        "entered_at": "2026-09-02T10:00:00Z",
        "stop_price": "1.09500",
        "target_price": "1.11030",
        "initial_risk": "98.1150",
        "closed_at": "2026-09-02T14:00:00Z",
        "average_close_price": "1.11030",
        "realized_pl": "196.1538",
        "financing": "-0.42",
        "dividend_adjustment": "0",
        "exit_cause": "TAKE_PROFIT",
    }


def test_history_keeps_eligible_trade_when_ineligible_observation_fills_sql_limit() -> (
    None
):
    session = _SqlLimitAwareSession(
        [
            _row(observation=_trade_observation(state="OPEN", close_time=None)),
            _row(observation=_trade_observation()),
        ],
        sql_limit=1,
    )

    items = PaperTradeHistoryReadService().list(cast(Session, session), limit=1)

    assert len(items) == 1
    assert items[0].closed_at == "2026-09-02T14:00:00Z"


def test_history_composes_exact_stop_loss_cause() -> None:
    item = PaperTradeHistoryReadService().list(
        cast(
            Session,
            _Session(
                [_row()],
                [_transaction_observation(cause="STOP_LOSS")],
            ),
        )
    )[0]

    assert item.exit_cause == "STOP_LOSS"


def test_history_orders_newest_close_first_and_applies_limit() -> None:
    older_id = uuid4()
    newer_id = uuid4()
    older = _attempt(attempt_id=older_id)
    newer = _attempt(attempt_id=newer_id, trade_id="7002")
    rows = [
        _row(
            attempt=older,
            observation=_trade_observation(older_id, close_time="2026-09-02T12:00:00Z"),
        ),
        _row(
            attempt=newer,
            observation=_trade_observation(
                newer_id,
                close_time="2026-09-02T15:00:00Z",
                trade_id="7002",
                provider_trade_id="7002",
            ),
        ),
    ]

    items = PaperTradeHistoryReadService().list(cast(Session, _Session(rows)), limit=1)

    assert len(items) == 1
    assert items[0].closed_at == "2026-09-02T15:00:00Z"


def test_history_orders_by_parsed_close_time_then_attempt_id() -> None:
    low_tie_id = UUID("00000000-0000-0000-0000-000000000001")
    high_tie_id = UUID("00000000-0000-0000-0000-000000000002")
    newest_id = UUID("00000000-0000-0000-0000-000000000003")
    rows = [
        (
            _attempt(attempt_id=low_tie_id),
            SimpleNamespace(name="Tie Low"),
            _trade_observation(
                low_tie_id,
                close_time="2026-09-02T15:00:00+02:00",
            ),
        ),
        (
            _attempt(attempt_id=newest_id, trade_id="7002"),
            SimpleNamespace(name="Newest"),
            _trade_observation(
                newest_id,
                close_time="2026-09-02T14:30:00Z",
                trade_id="7002",
                provider_trade_id="7002",
            ),
        ),
        (
            _attempt(attempt_id=high_tie_id, trade_id="7003"),
            SimpleNamespace(name="Tie High"),
            _trade_observation(
                high_tie_id,
                close_time="2026-09-02T15:00:00+02:00",
                trade_id="7003",
                provider_trade_id="7003",
            ),
        ),
    ]

    items = PaperTradeHistoryReadService().list(cast(Session, _Session(rows)), limit=3)

    assert [item.strategy_name for item in items] == [
        "Newest",
        "Tie High",
        "Tie Low",
    ]
    assert [item.closed_at for item in items] == [
        "2026-09-02T14:30:00Z",
        "2026-09-02T13:00:00Z",
        "2026-09-02T13:00:00Z",
    ]


@pytest.mark.parametrize("limit", [0, 51, True, 1.0])
def test_history_limit_is_bounded(limit: object) -> None:
    with pytest.raises(PaperTradeHistoryReadError, match="between 1 and 50"):
        PaperTradeHistoryReadService().list(
            cast(Session, _Session([])),
            limit=limit,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "attempt, observation",
    [
        (_attempt(trade_id=None), _trade_observation()),
        (_attempt(lifecycle="CONSISTENT"), _trade_observation()),
        (_attempt(), None),
        (_attempt(), _trade_observation(schema="ATLAS_PAPER_BROKER_FACTS_V1")),
        (
            _attempt(),
            SimpleNamespace(
                attempt_id=ATTEMPT_ID,
                normalized_schema_version="ATLAS_PAPER_BROKER_FACTS_V2",
                read_kind="TRADE_DETAIL",
                object_kind="TRADE",
                provider_trade_id=TRADE_ID,
                normalized_facts={
                    **_trade_observation().normalized_facts,
                    "realized_pl": "not-a-decimal",
                },
            ),
        ),
    ],
)
def test_history_fails_closed_for_ineligible_or_malformed_closure(
    attempt: SimpleNamespace,
    observation: SimpleNamespace | None,
) -> None:
    rows = (
        [] if observation is None else [_row(attempt=attempt, observation=observation)]
    )

    assert PaperTradeHistoryReadService().list(cast(Session, _Session(rows))) == ()


@pytest.mark.parametrize(
    "transaction",
    [
        None,
        _transaction_observation(transaction_id="99"),
        _transaction_observation(trade_id="other"),
        _transaction_observation(schema="ATLAS_PAPER_BROKER_FACTS_V1"),
        SimpleNamespace(
            attempt_id=ATTEMPT_ID,
            normalized_schema_version="ATLAS_PAPER_BROKER_FACTS_V2",
            read_kind="TRANSACTION_DETAIL",
            object_kind="TRANSACTION",
            provider_transaction_id="43",
            provider_trade_id=TRADE_ID,
            normalized_facts={
                "transaction_id": "43",
                "closed_trade_id": TRADE_ID,
                "exit_cause": "UNRESOLVED",
            },
        ),
    ],
)
def test_history_requires_matching_exact_transaction_evidence(
    transaction: SimpleNamespace | None,
) -> None:
    transactions = [] if transaction is None else [transaction]

    item = PaperTradeHistoryReadService().list(
        cast(Session, _Session([_row()], transactions))
    )[0]

    assert item.exit_cause is None


def test_history_does_not_promote_one_cause_from_multiple_closes() -> None:
    row = _row(
        observation=_trade_observation(closing_ids=["43", "44"]),
    )

    item = PaperTradeHistoryReadService().list(
        cast(
            Session,
            _Session(
                [row],
                [
                    _transaction_observation(),
                    _transaction_observation(transaction_id="44"),
                ],
            ),
        )
    )[0]

    assert item.exit_cause is None
