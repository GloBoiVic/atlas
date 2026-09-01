from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.domain.broker import (
    AccountIdentity,
    AccountSnapshot,
    ExecutableQuote,
    VenueInstrumentFacts,
)
from backend.domain.market_data import (
    Bar,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.domain.strategy import (
    Action,
    Direction,
    EntryPolicy,
    PendingEntryHandoff,
    TargetProposal,
)
from backend.execution import Order
from backend.market_data.live import LiveDataError, SparseM1ExecutionObservation
from backend.risk import PaperRiskService, TradeIntent
from backend.runtime.coordinator import BrokerRead, RuntimeDeployment
from backend.runtime.production import (
    OandaLiveDataSource,
    PendingOrderResolution,
    PendingPaperEntry,
    ProductionPaperComposition,
)
from backend.runtime.reconciliation import OandaReadOnlyBrokerReader
from backend.strategies.production import create_production_strategy_registry

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
DEPLOYMENT = RuntimeDeployment(uuid4(), "101-1", "RUNNING", "STARTING")


def _bar(start: datetime, timeframe: Timeframe, component: PriceComponent) -> Bar:
    interval = timedelta(minutes=15 if timeframe is Timeframe.M15 else 1)
    return Bar(
        Instrument.EUR_USD,
        timeframe,
        component,
        start,
        start + interval,
        Decimal("1.1000"),
        Decimal("1.1010"),
        Decimal("1.0990"),
        Decimal("1.1005"),
    )


class RecordedLiveSource:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_completed_native_m15(self, start, end, *, as_of):
        self.calls.append("M15")
        return SimpleNamespace(
            bars=(
                _bar(end - timedelta(minutes=15), Timeframe.M15, PriceComponent.MID),
            ),
            incomplete=(),
        )

    def fetch_completed_execution_m1(self, start, end, *, as_of):
        self.calls.append("M1")
        return SimpleNamespace(
            bars=(
                _bar(end - timedelta(minutes=1), Timeframe.M1, PriceComponent.BID),
                _bar(end - timedelta(minutes=1), Timeframe.M1, PriceComponent.ASK),
            )
        )


def test_production_live_composition_reads_native_products_separately() -> None:
    source = RecordedLiveSource()
    cycle = OandaLiveDataSource(source, warmup_bars=1).poll(DEPLOYMENT, NOW)

    assert source.calls == ["M15", "M1"]
    assert cycle.warmup_m15 == ()
    assert len(cycle.completed_m15) == 1
    assert len(cycle.execution_m1) == 1
    assert cycle.execution_m1[0].start_time > cycle.completed_m15[0].start_time


def test_production_live_composition_blocks_incomplete_analytical_candle() -> None:
    source = RecordedLiveSource()
    source.fetch_completed_native_m15 = lambda *args, **kwargs: SimpleNamespace(
        bars=(), incomplete=(SimpleNamespace(),)
    )

    with pytest.raises(LiveDataError, match="incomplete analytical M15"):
        OandaLiveDataSource(source, warmup_bars=1).poll(DEPLOYMENT, NOW)

    assert source.calls == []


def test_restart_loads_100_bar_context_and_post_frontier_catch_up() -> None:
    frontier = NOW - timedelta(minutes=30)
    context = tuple(
        _bar(
            frontier - timedelta(minutes=15 * (100 - index)),
            Timeframe.M15,
            PriceComponent.MID,
        )
        for index in range(100)
    )
    catch_up = (
        _bar(frontier, Timeframe.M15, PriceComponent.MID),
        _bar(frontier + timedelta(minutes=15), Timeframe.M15, PriceComponent.MID),
    )

    class RestartSource:
        def fetch_completed_native_m15(self, start, end, *, as_of):
            return SimpleNamespace(bars=(*context, *catch_up), incomplete=())

    cycle = OandaLiveDataSource(RestartSource()).restore(  # type: ignore[arg-type]
        DEPLOYMENT,
        NOW,
        frontier,
    )

    assert cycle.warmup_m15 == context
    assert cycle.completed_m15 == catch_up
    assert cycle.catch_up is True


def test_production_composition_contains_pure_risk_and_no_submission_transport(
) -> None:
    registry = create_production_strategy_registry()
    composition = ProductionPaperComposition(
        source=RecordedLiveSource(),  # type: ignore[arg-type]
        registry=registry,
        store=object(),
        market=SimpleNamespace(),  # type: ignore[arg-type]
    )

    assert isinstance(composition.risk, PaperRiskService)
    assert composition.execution.__class__.__name__ == "OandaExecutionAdapter"
    assert not hasattr(composition.execution, "submit_market_fok")


def test_readonly_reader_gets_transaction_and_protection_evidence() -> None:
    class Transport:
        def list_accounts(self):
            return {"accounts": [{"id": "101-1", "mt4AccountID": None}]}

        def account_summary(self, account_id):
            return {
                "account": {
                    "id": account_id,
                    "currency": "USD",
                    "balance": "10000",
                    "NAV": "10000",
                    "unrealizedPL": "0",
                    "marginAvailable": "9000",
                    "marginUsed": "1000",
                    "orders": [],
                    "trades": [
                        {
                            "id": "trade-1",
                            "instrument": "EUR_USD",
                            "currentUnits": "10",
                            "initialUnits": "10",
                        }
                    ],
                    "positions": [
                        {
                            "instrument": "EUR_USD",
                            "long": {
                                "units": "10",
                                "openTradeIDs": ["trade-1"],
                            },
                            "short": {"units": "0", "openTradeIDs": []},
                        }
                    ],
                },
                "lastTransactionID": "9",
            }

        def instrument(self, account_id, instrument="EUR_USD"):
            return {
                "instruments": [
                    {
                        "name": instrument,
                        "pipLocation": -4,
                        "displayPrecision": 5,
                        "tradeUnitsPrecision": 0,
                        "minimumTradeSize": "1",
                        "maximumOrderUnits": "1000000",
                        "maximumPositionSize": "1000000",
                        "marginRate": "0.02",
                        "orderTypes": ["MARKET", "STOP_LOSS", "TAKE_PROFIT"],
                    }
                ]
            }

        def pricing(self, account_id, instrument="EUR_USD"):
            return {
                "prices": [
                    {
                        "instrument": instrument,
                        "time": "2026-08-30T12:00:00Z",
                        "bids": [{"price": "1.1000"}],
                        "asks": [{"price": "1.1002"}],
                        "tradeable": True,
                    }
                ]
            }

        def trade(self, account_id, trade_id):
            return {
                "trade": {
                    "id": trade_id,
                    "state": "OPEN",
                    "currentUnits": "10",
                    "initialUnits": "10",
                    "stopLossOrder": {"id": "stop-1", "price": "1.0900"},
                    "takeProfitOrder": {"id": "target-1", "price": "1.1170"},
                }
            }

        def account_changes(self, account_id, since_transaction_id=None):
            return {
                "accountID": account_id,
                "lastTransactionID": "10",
                "changes": {
                    "transactions": [
                        {
                            "id": "10",
                            "type": "ORDER_FILL",
                            "orderID": "order-1",
                            "instrument": "EUR_USD",
                        }
                    ]
                },
            }

    result = OandaReadOnlyBrokerReader(
        Transport(), transaction_cursor=lambda _: "9"
    ).read(DEPLOYMENT, NOW)

    assert result.protection_verified is True
    assert result.protection_facts[0].trade_id == "trade-1"
    assert result.transactions_known is True
    assert result.transaction_fence == "10"
    assert result.transactions[0].external_order_id == "order-1"


def test_readonly_reader_uses_account_fence_for_cursorless_baseline_without_changes(
) -> None:
    calls: list[tuple[str, object]] = []

    class FlatTransport:
        def list_accounts(self):
            return {"accounts": [{"id": "101-1", "mt4AccountID": None}]}

        def account_summary(self, account_id):
            return {
                "account": {
                    "id": account_id,
                    "currency": "USD",
                    "balance": "10000",
                    "NAV": "10000",
                    "unrealizedPL": "0",
                    "marginAvailable": "9000",
                    "marginUsed": "1000",
                    "orders": [],
                    "trades": [],
                    "positions": [],
                },
                "lastTransactionID": "10",
            }

        def instrument(self, account_id, instrument="EUR_USD"):
            return {
                "instruments": [
                    {
                        "name": instrument,
                        "pipLocation": -4,
                        "displayPrecision": 5,
                        "tradeUnitsPrecision": 0,
                        "minimumTradeSize": "1",
                        "maximumOrderUnits": "1000000",
                        "maximumPositionSize": "1000000",
                        "marginRate": "0.02",
                        "orderTypes": ["MARKET", "STOP_LOSS", "TAKE_PROFIT"],
                    }
                ]
            }

        def pricing(self, account_id, instrument="EUR_USD"):
            return {
                "prices": [
                    {
                        "instrument": instrument,
                        "time": "2026-08-30T12:00:00Z",
                        "bids": [{"price": "1.1000"}],
                        "asks": [{"price": "1.1002"}],
                        "tradeable": True,
                    }
                ]
            }

        def account_changes(self, account_id, since_transaction_id=None):
            calls.append((account_id, since_transaction_id))
            raise AssertionError("cursorless baseline must not request Account Changes")

    result = OandaReadOnlyBrokerReader(
        FlatTransport(), transaction_cursor=lambda _: None
    ).read(DEPLOYMENT, NOW)

    assert result.transactions == ()
    assert result.transactions_known is False
    assert result.transaction_fence == "10"
    assert calls == []


def test_production_composition_authorizes_only_after_explicit_capital_gate() -> None:
    pending = PendingPaperEntry(
        uuid4(),
        TradeIntent(
            Action.OPEN_LONG,
            Direction.LONG,
            Decimal("1.0950"),
            TargetProposal(multiple=Decimal("1.7")),
        ),
        uuid4(),
    )
    identity = AccountIdentity("101-1")
    account = AccountSnapshot(
        identity,
        Decimal("10000"),
        Decimal("10000"),
        Decimal("0"),
        Decimal("10000"),
        Decimal("9000"),
        Decimal("1000"),
        NOW,
        "recorded",
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )
    instrument = VenueInstrumentFacts(
        VenueInstrument(
            Instrument.EUR_USD,
            Provider.OANDA,
            "EUR_USD",
        ),
        -4,
        5,
        0,
        Decimal("1"),
        Decimal("1000000"),
        Decimal("1000000"),
        Decimal("0.02"),
        frozenset({"LONG", "SHORT", "MARKET", "STOP_LOSS", "TAKE_PROFIT"}),
    )
    quote = ExecutableQuote(
        Instrument.EUR_USD,
        Decimal("1.1000"),
        Decimal("1.1002"),
        NOW,
        "recorded",
        True,
    )

    class Store:
        def __init__(self) -> None:
            self.events: list[str] = []

        def strategy_runtime_inputs(self, deployment_id):
            from backend.strategies.production import (
                EmaSweepConfirmationBreakCompatibilityAdaptor,
            )

            return (
                SimpleNamespace(
                    id=uuid4(),
                    state_schema_version=2,
                    required_historical_context_bars=100,
                    primary_timeframe=Timeframe.M15,
                ),
                SimpleNamespace(),
                EmaSweepConfirmationBreakCompatibilityAdaptor.initial_state(),
            )

        def persist_strategy_state(self, *args) -> None:
            self.events.append("STATE")

        def completed_m15_frontier(self, deployment_id):
            from backend.market_data.live import CompletedM15Frontier

            return CompletedM15Frontier()

        def validate_strategy_continuity(self, deployment_id, state) -> None:
            return None

        def pending_paper_entry(self, deployment_id):
            return pending

        def paper_risk_config(self, deployment_id):
            from backend.risk import PaperRiskConfig

            return PaperRiskConfig(Decimal("0.01"))

        def reconciliation_facts(self, deployment_id):
            return {"position": {"state": "FLAT"}}

        def persist_risk_decision(self, intent_id, decision, evaluated_at):
            self.events.append(decision.phase.value)
            return uuid4()

        def entry_order_resolution(self, deployment_id, intent_id):
            return None

        def create_pending_order(
            self, deployment, handoff, decision, persisted_decision_id
        ):
            order = Order(
                uuid4(),
                "MARKET",
                "ENTRY",
                "LONG",
                decision.quantity,
                client_correlation_id="atlas-paper-test",
                time_in_force="FOK",
                price_bound=decision.price_bound,
                stop_loss_price=decision.stop_price,
            )
            self.events.append("PENDING_SUBMISSION")
            return PendingOrderResolution(order, True, "PENDING_SUBMISSION")

        def apply_execution_result(self, deployment_id, result):
            self.events.append("FILL")

        def record_protection(self, deployment_id, order_id, state):
            self.events.append("PROTECTION")

        def record_protection_failure(self, deployment_id, reason):
            raise AssertionError(reason)

    class Transport:
        def __init__(self, store) -> None:
            self.store = store
            self.calls: list[str] = []
            self.submitted_units = Decimal("0")

        def submit_market_fok(self, account_id, payload):
            self.calls.append("submit")
            self.store.events.append("NETWORK")
            order = payload["order"]
            units = order["units"]
            self.submitted_units = abs(Decimal(units))
            return {
                "orderCreateTransaction": {"id": "20"},
                "orderFillTransaction": {
                    "id": "21",
                    "units": units,
                    "price": "1.1002",
                    "time": "2026-08-30T12:00:01Z",
                    "commission": "0",
                    "tradeOpened": {"tradeID": "30"},
                },
                "relatedTransactionIDs": ["20", "21"],
                "lastTransactionID": "21",
            }

        def attach_take_profit(self, account_id, trade_id, payload):
            self.calls.append("target")
            return {
                "trade": {
                    "id": trade_id,
                    "state": "OPEN",
                    "currentUnits": str(self.submitted_units),
                    "initialUnits": str(self.submitted_units),
                    "stopLossOrder": {"id": "31", "price": "1.0950"},
                    "takeProfitOrder": {
                        "id": "32",
                        "price": payload["takeProfit"]["price"],
                    },
                }
            }

        def trade(self, account_id, trade_id):
            self.calls.append("confirm")
            return self.attach_take_profit(account_id, trade_id, {
                "takeProfit": {"price": "1.10904"}
            })

    store = Store()
    transport = Transport(store)
    composition = ProductionPaperComposition(
        source=RecordedLiveSource(),
        registry=SimpleNamespace(
            implementation_for_version=lambda version: SimpleNamespace(
                definition=SimpleNamespace(
                    required_historical_context_bars=100,
                    state_schema_version=2,
                    primary_timeframe=version.primary_timeframe,
                )
            )
        ),
        store=store,
        market=SimpleNamespace(),  # type: ignore[arg-type]
        broker_reader=lambda deployment, now: BrokerRead(account, instrument, quote),
        execution_transport=transport,
        capital_actions_enabled=True,
        clock=lambda: NOW,
    )
    running_deployment = RuntimeDeployment(
        DEPLOYMENT.id, DEPLOYMENT.account_id, "RUNNING", "RUNNING"
    )
    processor = composition.processor_for(running_deployment)
    processor.processor.pending_entry = PendingEntryHandoff(
        EntryPolicy.PRICE_TRIGGERED,
        Direction.LONG,
        Decimal("1.1001"),
        PriceComponent.ASK,
        NOW - timedelta(minutes=1),
        NOW - timedelta(minutes=1),
        5,
    )
    assert processor.execution_processor is not None
    processor.execution_processor(running_deployment, _observation(NOW), True)

    assert store.events.index("PENDING_SUBMISSION") < store.events.index("NETWORK")
    assert store.events[-2:] == ["FILL", "PROTECTION"]
    assert transport.calls == ["submit", "target", "confirm", "target"]

    # A repeated observation cannot resubmit the same persisted handoff after
    # a terminal execution outcome; restart recovery belongs to reconciliation.
    processor.execution_processor(running_deployment, _observation(NOW), True)
    assert transport.calls == ["submit", "target", "confirm", "target"]


def _observation(start: datetime) -> SparseM1ExecutionObservation:
    return SparseM1ExecutionObservation(
        _bar(start, Timeframe.M1, PriceComponent.BID),
        _bar(start, Timeframe.M1, PriceComponent.ASK),
    )
