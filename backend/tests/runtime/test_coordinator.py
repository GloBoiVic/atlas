from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.domain.broker import (
    AccountIdentity,
    AccountSnapshot,
    BrokerPositionSide,
    BrokerProtectionFact,
    BrokerTradeFact,
    BrokerTransactionFact,
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
from backend.domain.strategy import Direction
from backend.market_data.live import CompletedM15Frontier
from backend.runtime.coordinator import (
    ActualState,
    BrokerRead,
    ChronologicalDataProcessor,
    ReadOnlyReconciler,
    ReconciliationOutcome,
    ReconciliationResult,
    RuntimeCommand,
    RuntimeCoordinator,
    RuntimeCycle,
    RuntimeDeployment,
    RuntimeReadiness,
    session_policy_is_pinned,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
DEPLOYMENT_ID = uuid4()
POLICY = {
    "session_policy_provenance": {
        "source_url": "https://developer.oanda.com/session-hours",
        "title": "FX session hours",
        "retrieved_at": "2026-08-30",
        "effective_interval": "2026-01-01/2026-12-31",
        "timezone": "America/New_York",
    }
}


class Lease:
    def __init__(self) -> None:
        self.released = False

    def release(self) -> None:
        self.released = True


class Store:
    def __init__(self, *, actual: str = "DRAFT") -> None:
        self.row = RuntimeDeployment(DEPLOYMENT_ID, "101-1", "DRAFT", actual, POLICY)
        self.states: list[tuple[str, str | None]] = []
        self.heartbeats: list[str] = []
        self.heartbeat_flags: list[bool] = []
        self.reconciliations: list[str] = []
        self.acquire_calls = 0

    def eligible_deployments(self):
        return (self.row,) if self.row.desired_state != "DRAFT" else ()

    def get_deployment(self, deployment_id):
        return self.row if deployment_id == self.row.id else None

    def request_state(self, deployment_id, desired_state):
        assert deployment_id == self.row.id
        self.row = RuntimeDeployment(
            self.row.id,
            self.row.account_id,
            desired_state,
            self.row.actual_state,
            self.row.execution_provenance,
        )
        return self.row

    def set_actual_state(self, deployment_id, actual_state, reason=None):
        assert deployment_id == self.row.id
        self.states.append((actual_state, reason))
        self.row = RuntimeDeployment(
            self.row.id,
            self.row.account_id,
            self.row.desired_state,
            actual_state,
            self.row.execution_provenance,
        )
        return self.row

    def heartbeat(self, deployment_id, owner_id, **kwargs):
        self.heartbeats.append(kwargs["health_status"])
        self.heartbeat_flags.append(kwargs["lock_held"])

    def record_reconciliation(self, deployment_id, **kwargs):
        self.reconciliations.append(kwargs["trigger"])


class Reconciler:
    def __init__(self, result):
        self.result = result
        self.calls: list[str] = []

    def reconcile(self, deployment, trigger, now):
        self.calls.append(trigger)
        return self.result


class BrokerReader:
    def __init__(self, value):
        self.value = value

    def read(self, deployment, now):
        return self.value


class CursorGateStore(Store):
    """Small durable-cursor seam used by the lifecycle gate regressions."""

    def __init__(self, *, cursor: str | None = None, fail_application: bool = False):
        super().__init__()
        self.cursor = cursor
        self.fail_application = fail_application
        self.repair_calls = 0
        self.timeline: list[str] = []

    def reconciliation_facts(self, deployment_id):
        return {
            "position": {"state": "FLAT"},
            "orders": [],
            "fills": [],
            "trades": [],
            "transaction_cursor": self.cursor,
        }

    def repair_reconciliation(self, deployment, broker):
        self.repair_calls += 1
        if self.fail_application:
            return ReconciliationResult(
                ReconciliationOutcome.RECONCILIATION_REQUIRED,
                {"reason": "ACCOUNT_CHANGES_APPLICATION_FAILED"},
                broker,
                "ACCOUNT_CHANGES_APPLICATION_FAILED",
            )
        assert broker.transaction_fence is not None
        self.cursor = broker.transaction_fence
        self.timeline.append("durable_cursor")
        return ReconciliationResult(
            ReconciliationOutcome.REPAIRED,
            {"cursor_after": self.cursor},
            broker,
            durable_gate_proven=True,
        )

    def set_actual_state(self, deployment_id, actual_state, reason=None):
        self.timeline.append(actual_state)
        return super().set_actual_state(deployment_id, actual_state, reason)

    def record_reconciliation(self, deployment_id, **kwargs):
        self.timeline.append("reconciliation_record")
        super().record_reconciliation(deployment_id, **kwargs)


class CursorGateReader:
    def __init__(self, store: CursorGateStore, value: BrokerRead):
        self.store = store
        self.value = value
        self.requested_cursors: list[str | None] = []

    def read(self, deployment, now):
        _ = deployment, now
        self.requested_cursors.append(self.store.cursor)
        return replace(
            self.value,
            transactions_known=self.store.cursor is not None,
            transaction_fence="10",
        )


def broker_read(*, open_position: bool = False) -> BrokerRead:
    identity = AccountIdentity("101-1")
    snapshot = AccountSnapshot(
        identity,
        Decimal("10000"),
        Decimal("10000"),
        Decimal("0"),
        Decimal("10000"),
        Decimal("10000"),
        Decimal("0"),
        NOW,
        "recorded",
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )
    if open_position:
        from backend.domain.broker import BrokerPositionSide
        from backend.domain.strategy import Direction

        snapshot = AccountSnapshot(
            identity,
            snapshot.balance,
            snapshot.nav,
            snapshot.unrealized_pl,
            snapshot.equity,
            snapshot.margin_available,
            snapshot.margin_used,
            NOW,
            "recorded",
            position_sides=(BrokerPositionSide(Direction.LONG, Decimal("10")),),
            orders_known=True,
            trades_known=True,
            positions_known=True,
        )
    instrument = VenueInstrumentFacts(
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
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
    return BrokerRead(
        snapshot, instrument, quote, protection_verified=not open_position
    )


def coordinator(store, reconciler, *, acquire=lambda _: Lease(), ready=True):
    return RuntimeCoordinator(
        store,
        reconciler,
        owner_id="test-runtime",
        acquire=acquire,
        clock=lambda: NOW,
        readiness=(lambda *_: RuntimeReadiness()) if ready else None,
    )


def test_start_records_desired_only_until_runtime_startup() -> None:
    store = Store()
    reconciler = Reconciler(
        ReconciliationResult(
            ReconciliationOutcome.MATCHED, {}, broker_read(), durable_gate_proven=True
        )
    )
    runtime = coordinator(store, reconciler)

    response = runtime.command(DEPLOYMENT_ID, RuntimeCommand.START)

    assert response.desired_state == "RUNNING"
    assert response.actual_state == ActualState.DRAFT.value
    assert reconciler.calls == []
    runtime.startup()
    assert store.row.actual_state == ActualState.RUNNING.value
    assert reconciler.calls == ["RUNTIME_START"]
    assert store.heartbeats[:1] == ["STARTING"]


def test_unpinned_session_policy_fails_closed_before_running() -> None:
    store = Store()
    store.row = RuntimeDeployment(
        store.row.id, store.row.account_id, "RUNNING", "DRAFT", {}
    )
    reconciler = Reconciler(
        ReconciliationResult(
            ReconciliationOutcome.MATCHED, {}, broker_read(), durable_gate_proven=True
        )
    )

    coordinator(store, reconciler, ready=False).startup()

    assert store.row.actual_state == ActualState.FAILED.value
    assert "provenance" in (store.row.actual_state and store.states[-1][1])


def test_lock_conflict_does_not_reconcile_or_run() -> None:
    store = Store()
    reconciler = Reconciler(
        ReconciliationResult(
            ReconciliationOutcome.MATCHED, {}, broker_read(), durable_gate_proven=True
        )
    )

    runtime = coordinator(store, reconciler, acquire=lambda _: None)
    runtime.command(DEPLOYMENT_ID, RuntimeCommand.START)
    runtime.startup()

    assert reconciler.calls == []
    assert store.row.actual_state == ActualState.FAILED.value


def test_persisted_running_reacquires_and_reconciles_before_running() -> None:
    store = Store(actual=ActualState.RUNNING.value)
    store.row = RuntimeDeployment(
        store.row.id, store.row.account_id, ActualState.RUNNING.value,
        ActualState.RUNNING.value, POLICY
    )
    reconciler = Reconciler(
        ReconciliationResult(
            ReconciliationOutcome.MATCHED, {}, broker_read(), durable_gate_proven=True
        )
    )
    acquired: list[UUID] = []

    def acquire(deployment_id: UUID) -> Lease:
        acquired.append(deployment_id)
        return Lease()

    runtime = coordinator(store, reconciler, acquire=acquire)
    runtime.startup()

    assert acquired == [DEPLOYMENT_ID]
    assert reconciler.calls == ["RUNTIME_START"]
    assert store.heartbeat_flags[0] is True
    assert store.row.actual_state == ActualState.RUNNING.value


def test_restart_restores_after_reconciliation_before_actual_running() -> None:
    store = Store()
    store.row = RuntimeDeployment(
        store.row.id, store.row.account_id, "RUNNING", "RUNNING", POLICY
    )
    events: list[str] = []

    class OrderedReconciler(Reconciler):
        def reconcile(self, deployment, trigger, now):
            events.append("reconcile")
            return super().reconcile(deployment, trigger, now)

    def restore(deployment, now):
        assert deployment.id == DEPLOYMENT_ID
        assert now == NOW
        events.append("restore")
        return ChronologicalDataProcessor(BarProcessor())

    def readiness(deployment, result, now):
        assert events == ["reconcile", "restore"]
        return RuntimeReadiness()

    runtime = RuntimeCoordinator(
        store,
        OrderedReconciler(
            ReconciliationResult(
                ReconciliationOutcome.MATCHED,
                {},
                broker_read(),
                durable_gate_proven=True,
            )
        ),
        owner_id="test-runtime",
        acquire=lambda _: Lease(),
        clock=lambda: NOW,
        readiness=readiness,
        restore_runtime=restore,
    )

    runtime.startup()

    assert store.row.actual_state == ActualState.RUNNING.value
    assert events == ["reconcile", "restore"]


def test_restart_restore_failure_blocks_before_actual_running() -> None:
    store = Store()
    store.row = RuntimeDeployment(
        store.row.id, store.row.account_id, "RUNNING", "RUNNING", POLICY
    )
    runtime = RuntimeCoordinator(
        store,
        Reconciler(
            ReconciliationResult(
                ReconciliationOutcome.MATCHED,
                {},
                broker_read(),
                durable_gate_proven=True,
            )
        ),
        owner_id="test-runtime",
        acquire=lambda _: Lease(),
        clock=lambda: NOW,
        readiness=lambda *_: RuntimeReadiness(),
        restore_runtime=lambda *_: (_ for _ in ()).throw(ValueError("invalid state")),
    )

    runtime.startup()

    assert store.row.actual_state == ActualState.FAILED.value
    assert "restoration" in (store.states[-1][1] or "")


def test_open_broker_trade_without_position_side_requires_reconciliation() -> None:
    broker = broker_read()
    account = AccountSnapshot(
        identity=broker.account.identity,
        balance=broker.account.balance,
        nav=broker.account.nav,
        unrealized_pl=broker.account.unrealized_pl,
        equity=broker.account.equity,
        margin_available=broker.account.margin_available,
        margin_used=broker.account.margin_used,
        observed_at=broker.account.observed_at,
        source=broker.account.source,
        open_trades=(
            BrokerTradeFact(
                "trade-1", Instrument.EUR_USD, Decimal("10"), Decimal("10")
            ),
        ),
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )
    result = ReadOnlyReconciler(
        BrokerReader(BrokerRead(account, broker.instrument, broker.quote))
    ).reconcile(
        RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "STARTING"),
        "RUNTIME_START",
        NOW,
    )

    assert result.outcome is ReconciliationOutcome.RECONCILIATION_REQUIRED
    assert result.reason == "BROKER_TRADE_POSITION_MISMATCH"


def test_local_flat_projection_cannot_override_broker_exposure() -> None:
    broker = broker_read()
    account = AccountSnapshot(
        identity=broker.account.identity,
        balance=broker.account.balance,
        nav=broker.account.nav,
        unrealized_pl=broker.account.unrealized_pl,
        equity=broker.account.equity,
        margin_available=broker.account.margin_available,
        margin_used=broker.account.margin_used,
        observed_at=broker.account.observed_at,
        source=broker.account.source,
        open_trades=(
            BrokerTradeFact(
                "trade-1", Instrument.EUR_USD, Decimal("10"), Decimal("10")
            ),
        ),
        position_sides=(
            BrokerPositionSide(
                Direction.LONG, Decimal("10"), trade_ids=("trade-1",)
            ),
        ),
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )
    result = ReadOnlyReconciler(
        BrokerReader(
            BrokerRead(
                account,
                broker.instrument,
                broker.quote,
                protection_verified=True,
                protection_facts=(
                    BrokerProtectionFact(
                        "trade-1", "stop-1", "target-1", Decimal("1"), Decimal("2")
                    ),
                ),
            )
        ),
        local_facts=lambda _: {"position": {"state": "FLAT"}},
    ).reconcile(
        RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "STARTING"),
        "RUNTIME_START",
        NOW,
    )

    assert result.outcome is ReconciliationOutcome.RECONCILIATION_REQUIRED
    assert result.reason == "LOCAL_BROKER_EXPOSURE_MISMATCH"


def test_stop_with_open_broker_position_is_blocked() -> None:
    store = Store(actual=ActualState.RUNNING.value)
    store.row = RuntimeDeployment(
        store.row.id, store.row.account_id, "STOPPED", ActualState.RUNNING.value, POLICY
    )
    reconciler = Reconciler(
        ReconciliationResult(
            ReconciliationOutcome.MATCHED,
            {},
            broker_read(open_position=True),
            durable_gate_proven=True,
        )
    )
    runtime = coordinator(store, reconciler)
    runtime._leases[DEPLOYMENT_ID] = Lease()

    runtime.cycle()

    assert store.row.actual_state == ActualState.RECONCILIATION_REQUIRED.value
    assert "STOP" in (store.states[-1][1] or "")


def test_reconciliation_failure_blocks_and_records_trigger() -> None:
    store = Store()
    store.row = RuntimeDeployment(
        store.row.id, store.row.account_id, "RUNNING", "DRAFT", POLICY
    )
    reconciler = Reconciler(
        ReconciliationResult(
            ReconciliationOutcome.RECONCILIATION_REQUIRED,
            {"reason": "BROKER_UNAVAILABLE"},
            reason="BROKER_UNAVAILABLE",
        )
    )

    coordinator(store, reconciler).startup()

    assert store.row.actual_state == ActualState.RECONCILIATION_REQUIRED.value
    assert store.reconciliations == ["RUNTIME_START"]


def test_heartbeat_failure_stops_cycle_before_data_processing() -> None:
    store = Store(actual=ActualState.RUNNING.value)
    store.row = RuntimeDeployment(
        store.row.id, store.row.account_id, ActualState.RUNNING.value,
        ActualState.RUNNING.value, POLICY
    )
    reconciler = Reconciler(
        ReconciliationResult(
            ReconciliationOutcome.MATCHED, {}, broker_read(), durable_gate_proven=True
        )
    )

    class FailingHeartbeatStore(Store):
        def __init__(self) -> None:
            super().__init__(actual=ActualState.RUNNING.value)
            self.row = store.row
            self.fail = False

        def heartbeat(self, deployment_id, owner_id, **kwargs):
            if self.fail:
                raise RuntimeError("database unavailable")
            super().heartbeat(deployment_id, owner_id, **kwargs)

    failing = FailingHeartbeatStore()
    polled: list[UUID] = []

    class Data:
        def poll(self, deployment, now):
            polled.append(deployment.id)
            return RuntimeCycle()

    runtime = RuntimeCoordinator(
        failing,
        reconciler,
        owner_id="test-runtime",
        acquire=lambda _: Lease(),
        clock=lambda: NOW,
        readiness=lambda *_: RuntimeReadiness(),
        data_source=Data(),
        data_processors={DEPLOYMENT_ID: ChronologicalDataProcessor(BarProcessor())},
    )
    runtime.startup()
    failing.fail = True

    runtime.cycle()

    assert polled == []
    assert failing.row.actual_state == ActualState.RECONCILIATION_REQUIRED.value


def test_read_only_reconciler_blocks_unverified_open_exposure() -> None:
    result = ReadOnlyReconciler(
        BrokerReader(broker_read(open_position=True))
    ).reconcile(
        RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "STARTING"),
        "RUNTIME_START",
        NOW,
    )

    assert result.outcome is ReconciliationOutcome.RECONCILIATION_REQUIRED
    assert result.reason == "PROTECTION_UNVERIFIED"


def test_read_only_reconciler_blocks_unknown_broker_state_collections() -> None:
    broker = broker_read()
    unknown = AccountSnapshot(
        identity=broker.account.identity,
        balance=broker.account.balance,
        nav=broker.account.nav,
        unrealized_pl=broker.account.unrealized_pl,
        equity=broker.account.equity,
        margin_available=broker.account.margin_available,
        margin_used=broker.account.margin_used,
        observed_at=broker.account.observed_at,
        source=broker.account.source,
        orders_known=True,
        trades_known=False,
        positions_known=True,
    )
    result = ReadOnlyReconciler(
        BrokerReader(
            BrokerRead(
                unknown,
                broker.instrument,
                broker.quote,
            )
        )
    ).reconcile(
        RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "STARTING"),
        "RUNTIME_START",
        NOW,
    )

    assert result.outcome is ReconciliationOutcome.RECONCILIATION_REQUIRED
    assert result.reason == "ACCOUNT_STATE_COLLECTIONS_UNKNOWN"


class BarProcessor:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, bool]] = []

    def process_completed_bar(self, deployment, bar, *, allow_entries):
        self.calls.append((bar.end_time, allow_entries))


def bar(start: datetime) -> Bar:
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        Decimal("1.1"),
        Decimal("1.2"),
        Decimal("1.0"),
        Decimal("1.1"),
    )


def test_catch_up_is_chronological_and_never_allows_stale_entries() -> None:
    processor = BarProcessor()
    previous = bar(NOW - timedelta(minutes=60))
    data = ChronologicalDataProcessor(
        processor, frontier=CompletedM15Frontier().accept(previous, NOW)
    )
    bars = tuple(
        bar(NOW - timedelta(minutes=45) + timedelta(minutes=15 * i)) for i in range(3)
    )

    assert (
        data.process(
            RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "RUNNING"),
            RuntimeCycle(completed_m15=bars, as_of=NOW, catch_up=True),
            NOW,
        )
        == 3
    )
    assert processor.calls == [
        (NOW - timedelta(minutes=30), False),
        (NOW - timedelta(minutes=15), False),
        (NOW, False),
    ]


def test_out_of_order_live_m15_blocks_before_strategy() -> None:
    processor = BarProcessor()
    data = ChronologicalDataProcessor(processor)
    bars = (
        bar(NOW - timedelta(minutes=15)),
        bar(NOW - timedelta(minutes=30)),
    )

    with pytest.raises(Exception, match="out-of-order"):
        data.process(
            RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "RUNNING"),
            RuntimeCycle(completed_m15=bars, as_of=NOW),
            NOW,
        )

    assert processor.calls == []


def test_session_policy_placeholder_is_not_pinned() -> None:
    assert session_policy_is_pinned({}) is False
    assert (
        session_policy_is_pinned(
            {
                "session_policy_provenance": {
                    **POLICY["session_policy_provenance"],
                    "title": "OANDA_DOC_PENDING",
                }
            }
        )
        is False
    )


def test_reconciliation_calls_durable_repair_for_clear_transaction_evidence() -> None:
    base = broker_read()
    account = AccountSnapshot(
        identity=base.account.identity,
        balance=base.account.balance,
        nav=base.account.nav,
        unrealized_pl=base.account.unrealized_pl,
        equity=base.account.equity,
        margin_available=base.account.margin_available,
        margin_used=base.account.margin_used,
        observed_at=NOW,
        source="recorded",
        open_trades=(
            BrokerTradeFact(
                "trade-1", Instrument.EUR_USD, Decimal("10"), Decimal("10")
            ),
        ),
        position_sides=(
            BrokerPositionSide(Direction.LONG, Decimal("10"), trade_ids=("trade-1",)),
        ),
        last_transaction_id="10",
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )
    broker = BrokerRead(
        account,
        base.instrument,
        base.quote,
        protection_verified=True,
        protection_facts=(
            BrokerProtectionFact(
                "trade-1", "stop-1", "target-1", Decimal("1"), Decimal("2")
            ),
        ),
        transactions=(
            BrokerTransactionFact(
                "10",
                "ORDER_FILL",
                "order-1",
                "trade-1",
                Decimal("10"),
                Decimal("1.1"),
                NOW,
            ),
        ),
        transactions_known=True,
    )
    repairs: list[UUID] = []

    def repair(deployment, facts):
        repairs.append(deployment.id)
        return ReconciliationResult(
            ReconciliationOutcome.REPAIRED,
            {"fills_applied": 1},
            facts,
            durable_gate_proven=True,
        )

    result = ReadOnlyReconciler(
        BrokerReader(broker),
        local_facts=lambda _: {
            "position": {"state": "FLAT"},
            "orders": [
                {
                    "external_order_id": "order-1",
                    "status": "UNKNOWN",
                }
            ],
            "fills": [],
            "transaction_cursor": "9",
        },
        repair=repair,
    ).reconcile(
        RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "STARTING"),
        "UNKNOWN_ORDER",
        NOW,
    )

    assert result.outcome is ReconciliationOutcome.REPAIRED
    assert repairs == [DEPLOYMENT_ID]


def test_reconciliation_keeps_cursor_gap_and_protection_ambiguity_blocked() -> None:
    base = broker_read()
    gap_account = AccountSnapshot(
        identity=base.account.identity,
        balance=base.account.balance,
        nav=base.account.nav,
        unrealized_pl=base.account.unrealized_pl,
        equity=base.account.equity,
        margin_available=base.account.margin_available,
        margin_used=base.account.margin_used,
        observed_at=NOW,
        source="recorded",
        last_transaction_id="11",
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )
    called = 0

    def repair(deployment, facts):
        nonlocal called
        called += 1
        return None

    result = ReadOnlyReconciler(
        BrokerReader(
            BrokerRead(
                gap_account,
                base.instrument,
                base.quote,
                transactions=(BrokerTransactionFact("10", "ORDER_CANCEL"),),
                transactions_known=True,
            )
        ),
        local_facts=lambda _: {
            "position": {"state": "FLAT"},
            "transaction_cursor": "9",
        },
        repair=repair,
    ).reconcile(
        RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "STARTING"),
        "RUNTIME_START",
        NOW,
    )
    assert result.outcome is ReconciliationOutcome.RECONCILIATION_REQUIRED
    assert result.reason == "TRANSACTION_CURSOR_GAP"
    assert called == 1

    blocked = ReadOnlyReconciler(
        BrokerReader(broker_read(open_position=True)),
        repair=lambda *_: (_ for _ in ()).throw(AssertionError("repair must not run")),
    ).reconcile(
        RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "STARTING"),
        "RUNTIME_START",
        NOW,
    )
    assert blocked.reason == "PROTECTION_UNVERIFIED"


@pytest.mark.parametrize(
    "lifecycle", ("START", "RESUME", "RECONNECT", "OWNERSHIP_REACQUISITION")
)
def test_cursorless_lifecycle_cannot_run_before_durable_baseline(
    lifecycle: str,
) -> None:
    store = CursorGateStore(fail_application=True)
    store.row = RuntimeDeployment(
        DEPLOYMENT_ID,
        "101-1",
        "PAUSED" if lifecycle == "RESUME" else "RUNNING",
        (
            "PAUSED"
            if lifecycle == "RESUME"
            else "DRAFT"
            if lifecycle == "START"
            else "RUNNING"
        ),
        POLICY,
    )
    reader = CursorGateReader(store, broker_read())
    reconciler = ReadOnlyReconciler(
        reader,
        local_facts=store.reconciliation_facts,
        repair=store.repair_reconciliation,
    )
    runtime = coordinator(store, reconciler)

    if lifecycle == "START":
        runtime.command(DEPLOYMENT_ID, RuntimeCommand.START)
        runtime.startup()
    elif lifecycle == "RESUME":
        runtime.command(DEPLOYMENT_ID, RuntimeCommand.RESUME)
        runtime.cycle()
    elif lifecycle == "RECONNECT":
        runtime._leases[DEPLOYMENT_ID] = Lease()
        runtime.reconnect()
    else:
        runtime.startup()

    assert store.row.actual_state == ActualState.RECONCILIATION_REQUIRED.value
    assert store.cursor is None
    assert store.repair_calls == 1


@pytest.mark.parametrize("unknown_kind", ("non_flat", "unknown"))
def test_cursorless_non_flat_or_unknown_account_blocks_baseline(
    unknown_kind: str,
) -> None:
    base = broker_read(open_position=unknown_kind == "non_flat")
    if unknown_kind == "unknown":
        account = replace(base.account, positions_known=False)
        base = replace(base, account=account)
    store = CursorGateStore()
    reader = CursorGateReader(store, base)
    result = ReadOnlyReconciler(
        reader,
        local_facts=store.reconciliation_facts,
        repair=store.repair_reconciliation,
    ).reconcile(
        RuntimeDeployment(DEPLOYMENT_ID, "101-1", "RUNNING", "STARTING"),
        "START",
        NOW,
    )

    assert result.outcome is ReconciliationOutcome.RECONCILIATION_REQUIRED
    assert store.cursor is None
    assert store.repair_calls == 0


def test_cursorless_baseline_is_durable_before_matched_and_running() -> None:
    store = CursorGateStore()
    reader = CursorGateReader(store, broker_read())
    runtime = coordinator(
        store,
        ReadOnlyReconciler(
            reader,
            local_facts=store.reconciliation_facts,
            repair=store.repair_reconciliation,
        ),
    )

    runtime.command(DEPLOYMENT_ID, RuntimeCommand.START)
    runtime.startup()

    assert store.row.actual_state == ActualState.RUNNING.value
    assert store.cursor == "10"
    assert store.timeline.index("durable_cursor") < store.timeline.index("RUNNING")


def test_stale_cursor_requires_account_changes_catch_up() -> None:
    store = CursorGateStore(cursor="9")
    reader = CursorGateReader(store, broker_read())
    runtime = coordinator(
        store,
        ReadOnlyReconciler(
            reader,
            local_facts=store.reconciliation_facts,
            repair=store.repair_reconciliation,
        ),
    )

    runtime.command(DEPLOYMENT_ID, RuntimeCommand.START)
    runtime.startup()

    assert store.row.actual_state == ActualState.RUNNING.value
    assert store.cursor == "10"
    assert reader.requested_cursors == ["9"]


def test_failed_account_changes_application_retains_cursor_and_blocks() -> None:
    store = CursorGateStore(cursor="9", fail_application=True)
    reader = CursorGateReader(store, broker_read())
    runtime = coordinator(
        store,
        ReadOnlyReconciler(
            reader,
            local_facts=store.reconciliation_facts,
            repair=store.repair_reconciliation,
        ),
    )

    runtime.command(DEPLOYMENT_ID, RuntimeCommand.START)
    runtime.startup()

    assert store.row.actual_state == ActualState.RECONCILIATION_REQUIRED.value
    assert store.cursor == "9"


def test_successful_catch_up_advances_cursor_before_matched() -> None:
    store = CursorGateStore(cursor="9")
    reader = CursorGateReader(store, broker_read())
    runtime = coordinator(
        store,
        ReadOnlyReconciler(
            reader,
            local_facts=store.reconciliation_facts,
            repair=store.repair_reconciliation,
        ),
    )

    runtime.command(DEPLOYMENT_ID, RuntimeCommand.START)
    runtime.startup()

    assert store.row.actual_state == ActualState.RUNNING.value
    assert store.cursor == "10"
    assert store.timeline.index("durable_cursor") < store.timeline.index(
        "reconciliation_record"
    )


def test_restart_reuses_persisted_cursor_for_account_changes() -> None:
    store = CursorGateStore()
    first_reader = CursorGateReader(store, broker_read())
    first = coordinator(
        store,
        ReadOnlyReconciler(
            first_reader,
            local_facts=store.reconciliation_facts,
            repair=store.repair_reconciliation,
        ),
    )
    first.command(DEPLOYMENT_ID, RuntimeCommand.START)
    first.startup()
    assert store.cursor == "10"

    store.row = RuntimeDeployment(
        DEPLOYMENT_ID, "101-1", "RUNNING", "RUNNING", POLICY
    )
    second_reader = CursorGateReader(store, broker_read())
    second = coordinator(
        store,
        ReadOnlyReconciler(
            second_reader,
            local_facts=store.reconciliation_facts,
            repair=store.repair_reconciliation,
        ),
    )
    second.startup()

    assert second_reader.requested_cursors == ["10"]
    assert store.cursor == "10"
    assert store.row.actual_state == ActualState.RUNNING.value
