"""The bounded PAPER runtime coordinator.

The coordinator is deliberately dependency-injected.  It owns lifecycle and
reconciliation decisions, while persistence, broker reads, and Strategy/data
composition remain explicit seams.  In particular, this module never imports
an authenticated execution transport and therefore cannot submit an Order as
part of startup or control handling.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol, cast
from uuid import UUID

from backend.domain.broker import (
    AccountIdentity,
    AccountSnapshot,
    BrokerProtectionFact,
    BrokerTransactionFact,
    ExecutableQuote,
    VenueInstrumentFacts,
)
from backend.domain.market_data import Bar
from backend.market_data.live import (
    CompletedM15Frontier,
    LiveDataError,
    SparseM1ExecutionObservation,
    analytical_bar_fingerprint,
    validate_completed_native_m15,
)


class RuntimeErrorBase(RuntimeError):
    """Base error for a runtime safety boundary."""


class RuntimeCommand(StrEnum):
    START = "START"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    STOP = "STOP"
    ARCHIVE = "ARCHIVE"
    RECONCILE = "RECONCILE"


class ActualState(StrEnum):
    DRAFT = "DRAFT"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    ARCHIVED = "ARCHIVED"


class ReconciliationOutcome(StrEnum):
    MATCHED = "MATCHED"
    REPAIRED = "REPAIRED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class RuntimeDeployment:
    """Only non-secret Deployment facts needed by the coordinator."""

    id: UUID
    account_id: str
    desired_state: str
    actual_state: str
    execution_provenance: Mapping[str, object] = field(
        default_factory=lambda: cast(dict[str, object], {})
    )
    trading_account: AccountIdentity | None = None

    def __post_init__(self) -> None:
        expected = self.trading_account or AccountIdentity(self.account_id)
        if expected.account_id != self.account_id:
            raise ValueError("Deployment account identity is inconsistent")
        object.__setattr__(self, "trading_account", expected)


@dataclass(frozen=True, slots=True)
class BrokerRead:
    """Normalized read-only broker facts used by reconciliation."""

    account: AccountSnapshot
    instrument: VenueInstrumentFacts
    quote: ExecutableQuote
    protection_verified: bool = True
    protection_facts: tuple[BrokerProtectionFact, ...] = ()
    transactions: tuple[BrokerTransactionFact, ...] = ()
    transactions_known: bool = False
    transaction_fence: str | None = None

    @property
    def has_open_position(self) -> bool:
        return self.account.has_open_position


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    outcome: ReconciliationOutcome
    summary: Mapping[str, object]
    broker: BrokerRead | None = None
    reason: str | None = None
    durable_gate_proven: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeReadiness:
    """Explicit gates required before actual RUNNING is persisted."""

    account_valid: bool = True
    capabilities_valid: bool = True
    session_policy_valid: bool = True
    state_valid: bool = True
    warmup_valid: bool = True
    data_fresh: bool = True
    protection_valid: bool = True
    reason: str | None = None

    @property
    def passed(self) -> bool:
        return all(
            (
                self.account_valid,
                self.capabilities_valid,
                self.session_policy_valid,
                self.state_valid,
                self.warmup_valid,
                self.data_fresh,
                self.protection_valid,
            )
        )


@dataclass(frozen=True, slots=True)
class RuntimeCycle:
    """A deterministic batch of native analytical and execution observations."""

    warmup_m15: tuple[Bar, ...] = ()
    completed_m15: tuple[Bar, ...] = ()
    execution_m1: tuple[SparseM1ExecutionObservation, ...] = ()
    as_of: datetime | None = None
    catch_up: bool = False


class RuntimeLease(Protocol):
    def release(self) -> None: ...


class RuntimeStore(Protocol):
    """Persistence seam; implementations own short database transactions."""

    def eligible_deployments(self) -> Sequence[RuntimeDeployment]: ...

    def get_deployment(self, deployment_id: UUID) -> RuntimeDeployment | None: ...

    def request_state(
        self, deployment_id: UUID, desired_state: str
    ) -> RuntimeDeployment: ...

    def set_actual_state(
        self, deployment_id: UUID, actual_state: str, reason: str | None = None
    ) -> RuntimeDeployment: ...

    def heartbeat(
        self,
        deployment_id: UUID,
        owner_id: str,
        *,
        lock_held: bool,
        db_connected: bool,
        health_status: str,
        details: Mapping[str, object] | None = None,
    ) -> None: ...

    def record_reconciliation(
        self,
        deployment_id: UUID,
        *,
        trigger: str,
        outcome: ReconciliationOutcome,
        started_at: datetime,
        finished_at: datetime,
        summary: Mapping[str, object],
        broker: BrokerRead | None = None,
    ) -> None: ...

    def reconciliation_facts(self, deployment_id: UUID) -> Mapping[str, object]: ...

    def repair_reconciliation(
        self, deployment: RuntimeDeployment, broker: BrokerRead
    ) -> ReconciliationResult | None: ...


class BrokerReader(Protocol):
    def read(self, deployment: RuntimeDeployment, now: datetime) -> BrokerRead: ...


class Reconciler(Protocol):
    def reconcile(
        self, deployment: RuntimeDeployment, trigger: str, now: datetime
    ) -> ReconciliationResult: ...


class RuntimeDataSource(Protocol):
    def poll(self, deployment: RuntimeDeployment, now: datetime) -> RuntimeCycle: ...


class BarProcessor(Protocol):
    def process_completed_bar(
        self, deployment: RuntimeDeployment, bar: Bar, *, allow_entries: bool
    ) -> None: ...


class HistoricalContextSeeder(Protocol):
    def seed_historical_context(
        self,
        bars: tuple[Bar, ...],
        *,
        as_of: datetime,
        durable_frontier: datetime | None,
    ) -> None: ...


ExecutionProcessor = Callable[
    [RuntimeDeployment, SparseM1ExecutionObservation, bool], None
]


class Clock(Protocol):
    def __call__(self) -> datetime: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class ReadOnlyReconciler:
    """Conservative reconciliation using normalized provider facts only."""

    def __init__(
        self,
        reader: BrokerReader,
        *,
        quote_max_age: timedelta = timedelta(minutes=2),
        local_facts: Callable[[UUID], Mapping[str, object]] | None = None,
        repair: Callable[
            [RuntimeDeployment, BrokerRead], ReconciliationResult | None
        ]
        | None = None,
    ) -> None:
        if quote_max_age <= timedelta(0):
            raise ValueError("quote_max_age must be positive")
        self.reader = reader
        self.quote_max_age = quote_max_age
        self.local_facts = local_facts
        self.repair = repair

    def reconcile(
        self, deployment: RuntimeDeployment, trigger: str, now: datetime
    ) -> ReconciliationResult:
        try:
            broker = self.reader.read(deployment, now)
            if broker.account.identity != deployment.trading_account:
                return self._required("ACCOUNT_IDENTITY_MISMATCH")
            if not broker.account.fresh:
                return self._required("ACCOUNT_STATE_STALE")
            if (
                broker.account.observed_at > now
                or now - broker.account.observed_at > timedelta(minutes=2)
            ):
                return self._required("ACCOUNT_STATE_STALE")
            if not broker.account.account_state_known:
                return self._required("ACCOUNT_STATE_COLLECTIONS_UNKNOWN")
            if not broker.instrument.available:
                return self._required("INSTRUMENT_UNAVAILABLE")
            if not broker.quote.is_fresh(now, self.quote_max_age):
                return self._required("QUOTE_STALE_OR_UNTRADEABLE")
            if broker.account.pending_orders:
                return self._required("PENDING_BROKER_ORDERS")
            if len(broker.account.open_trades) > 1:
                return self._required("MULTIPLE_OPEN_TRADES")
            directions = [
                side.direction.value
                for side in broker.account.position_sides
                if side.is_open
            ]
            if len(set(directions)) > 1:
                return self._required("OPPOSING_POSITION_SIDES")
            trade_mismatch = self._trade_position_mismatch(broker)
            if trade_mismatch is not None:
                return self._required(trade_mismatch)
            if broker.has_open_position and not broker.protection_verified:
                return self._required("PROTECTION_UNVERIFIED")
            if broker.has_open_position and not broker.protection_facts:
                return self._required("PROTECTION_FACTS_UNAVAILABLE")
            if broker.account.open_trades:
                protection_by_trade = {
                    item.trade_id: item for item in broker.protection_facts
                }
                if any(
                    not protection_by_trade.get(trade.external_id)
                    or not protection_by_trade[trade.external_id].matches(trade)
                    for trade in broker.account.open_trades
                    if trade.is_open
                ):
                    return self._required("PROTECTION_FACTS_MISMATCH")
            if self._requires_durable_gate(trigger) and self.local_facts is None:
                return self._required("LOCAL_RECONCILIATION_FACTS_UNAVAILABLE")
            if broker.transactions_known is False and trigger in {
                "UNCERTAIN_SUBMISSION",
                "UNKNOWN_ORDER",
                "MISSED_FILL",
            }:
                return self._required("TRANSACTION_HISTORY_UNAVAILABLE")
            if self.local_facts is not None:
                local = self._read_local_facts(deployment.id)
                if local is None:
                    return self._required("LOCAL_RECONCILIATION_FACTS_UNAVAILABLE")
                mismatch = self._local_mismatch(deployment.id, broker, local)
                if mismatch is not None:
                    if self.repair is not None:
                        repaired = self.repair(deployment, broker)
                        if (
                            repaired is not None
                            and repaired.outcome in {
                                ReconciliationOutcome.MATCHED,
                                ReconciliationOutcome.REPAIRED,
                            }
                        ):
                            return ReconciliationResult(
                                repaired.outcome,
                                repaired.summary,
                                repaired.broker or broker,
                                repaired.reason,
                                durable_gate_proven=True,
                            )
                    return self._required(mismatch)
                if self._requires_durable_gate(trigger):
                    if not self._transaction_gate_is_safe(local, broker):
                        return self._required(
                            self._transaction_gate_reason(local, broker)
                        )
                    if self.repair is None:
                        return self._required(
                            "DURABLE_RECONCILIATION_GATE_UNAVAILABLE"
                        )
                    repaired = self.repair(deployment, broker)
                    if (
                        repaired is None
                        or repaired.outcome not in {
                            ReconciliationOutcome.MATCHED,
                            ReconciliationOutcome.REPAIRED,
                        }
                    ):
                        return self._required(
                            repaired.reason
                            if repaired is not None and repaired.reason
                            else "DURABLE_RECONCILIATION_GATE_FAILED"
                        )
                    return ReconciliationResult(
                        repaired.outcome,
                        repaired.summary,
                        repaired.broker or broker,
                        repaired.reason,
                        durable_gate_proven=True,
                    )
            return ReconciliationResult(
                ReconciliationOutcome.MATCHED,
                {
                    "account": broker.account.identity.account_id,
                    "open_position": broker.has_open_position,
                    "pending_orders": len(broker.account.pending_orders),
                    "open_trades": len(broker.account.open_trades),
                    "trigger": trigger,
                },
                broker,
            )
        except Exception as error:
            # Provider exceptions are intentionally reduced to a stable reason;
            # credentials and raw provider diagnostics must not enter persistence.
            return self._required(type(error).__name__.upper())

    @staticmethod
    def _trade_position_mismatch(broker: BrokerRead) -> str | None:
        """Never infer FLAT from incomplete or contradictory broker facts."""

        open_trades = tuple(
            trade for trade in broker.account.open_trades if trade.is_open
        )
        open_sides = tuple(
            side for side in broker.account.position_sides if side.is_open
        )
        if not open_trades and not open_sides:
            return None
        if not open_trades:
            # A populated side with no corresponding Trade is not flat, but the
            # legacy read-only test seam may not expose trade details yet.
            return (
                None
                if not broker.protection_verified
                else "BROKER_TRADE_POSITION_MISMATCH"
            )
        for trade in open_trades:
            matching = tuple(
                side for side in open_sides if side.direction is trade.direction
            )
            if len(matching) != 1 or matching[0].units != trade.absolute_units:
                return "BROKER_TRADE_POSITION_MISMATCH"
            if matching[0].trade_ids and trade.external_id not in matching[0].trade_ids:
                return "BROKER_TRADE_POSITION_MISMATCH"
        if sum(side.units for side in open_sides) != sum(
            trade.absolute_units for trade in open_trades
        ):
            return "BROKER_TRADE_POSITION_MISMATCH"
        return None

    def _read_local_facts(self, deployment_id: UUID) -> Mapping[str, object] | None:
        reader = self.local_facts
        if reader is None:
            return None
        try:
            raw_local = cast(object, reader(deployment_id))
        except Exception:
            return None
        if not isinstance(raw_local, Mapping):
            return None
        return cast(Mapping[str, object], raw_local)

    @staticmethod
    def _requires_durable_gate(trigger: str) -> bool:
        _ = trigger
        return True

    @staticmethod
    def _transaction_gate_is_safe(
        local: Mapping[str, object], broker: BrokerRead
    ) -> bool:
        local_cursor = local.get("transaction_cursor")
        fence = broker.transaction_fence
        if fence is None or type(fence) is not str or not fence.isdecimal():
            return False
        if local_cursor is None:
            return not broker.transactions_known
        return (
            type(local_cursor) is str
            and local_cursor.isdecimal()
            and broker.transactions_known
            and int(fence) >= int(local_cursor)
        )

    @staticmethod
    def _transaction_gate_reason(
        local: Mapping[str, object], broker: BrokerRead
    ) -> str:
        local_cursor = local.get("transaction_cursor")
        fence = broker.transaction_fence
        if fence is None or type(fence) is not str or not fence.isdecimal():
            return "CURRENT_TRANSACTION_FENCE_UNAVAILABLE"
        if local_cursor is None:
            if broker.transactions_known:
                return "ACCOUNT_CHANGES_REQUIRES_DURABLE_CURSOR"
            return "INITIAL_CURSOR_BASELINE_UNAVAILABLE"
        if type(local_cursor) is not str or not local_cursor.isdecimal():
            return "LOCAL_TRANSACTION_CURSOR_INVALID"
        if not broker.transactions_known:
            return "TRANSACTION_HISTORY_UNAVAILABLE"
        if int(fence) < int(local_cursor):
            return "TRANSACTION_CURSOR_MOVED_BACKWARD"
        return "DURABLE_RECONCILIATION_GATE_FAILED"

    def _local_mismatch(
        self,
        deployment_id: UUID,
        broker: BrokerRead,
        raw_local: Mapping[str, object] | None = None,
    ) -> str | None:
        if raw_local is None:
            reader = self.local_facts
            try:
                raw_value = cast(
                    object, reader(deployment_id) if reader is not None else {}
                )
            except Exception:
                return "LOCAL_RECONCILIATION_FACTS_UNAVAILABLE"
            if not isinstance(raw_value, Mapping):
                return "LOCAL_RECONCILIATION_FACTS_INVALID"
            raw_local = cast(Mapping[str, object], raw_value)
        local = raw_local
        if local.get("unknown") is True:
            return "LOCAL_RECONCILIATION_FACTS_UNKNOWN"
        if local.get("repair_required") is True:
            return "LOCAL_REPAIR_REQUIRES_RECONCILIATION"
        local_position = local.get("position")
        if isinstance(local_position, Mapping):
            position = cast(Mapping[str, object], local_position)
            local_state = position.get("state")
            broker_exposed = broker.has_open_position
            if local_state == "FLAT" and broker_exposed:
                return "LOCAL_BROKER_EXPOSURE_MISMATCH"
            if local_state in {"LONG", "SHORT"} and not broker_exposed:
                return "LOCAL_BROKER_EXPOSURE_MISMATCH"
        local_orders = local.get("orders")
        local_order_external: set[str] = set()
        if isinstance(local_orders, (tuple, list)):
            order_items = cast(tuple[object, ...] | list[object], local_orders)
            typed_orders = tuple(
                cast(Mapping[str, object], item)
                for item in order_items
                if isinstance(item, Mapping)
            )
            unknown_orders = tuple(
                item
                for item in typed_orders
                if item.get("status") == "UNKNOWN"
            )
            if unknown_orders:
                return "UNKNOWN_ORDER_REQUIRES_RECONCILIATION"
            local_order_external = {
                str(item.get("external_order_id"))
                for item in typed_orders
                if item.get("external_order_id")
            }
            local_pending_external = {
                str(item.get("external_order_id"))
                for item in typed_orders
                if item.get("status") in {"PENDING_SUBMISSION", "SUBMITTED"}
                and item.get("external_order_id")
            }
            broker_external = {
                item.external_id for item in broker.account.pending_orders
            }
            if (
                local_pending_external
                and not local_pending_external.issubset(broker_external)
            ):
                return "LOCAL_BROKER_ORDER_MISMATCH"
        local_cursor = local.get("transaction_cursor")
        broker_cursor = broker.transaction_fence
        if local_cursor is not None:
            if (
                type(local_cursor) is not str
                or broker_cursor is None
                or not local_cursor.isdecimal()
                or not broker_cursor.isdecimal()
                or int(broker_cursor) < int(local_cursor)
            ):
                return "TRANSACTION_CURSOR_GAP"
            if int(broker_cursor) > int(local_cursor):
                # The complete unfiltered Account Changes response is the
                # provider fence; the store receipts every transaction before
                # advancing the durable cursor.
                if not broker.transactions_known:
                    return "TRANSACTION_HISTORY_UNAVAILABLE"
                return "TRANSACTION_CURSOR_GAP"
        local_fills = local.get("fills")
        if isinstance(local_fills, (tuple, list)) and broker.transactions:
            fill_ids = {
                str(cast(Mapping[str, object], item).get("external_transaction_id"))
                for item in cast(tuple[object, ...] | list[object], local_fills)
                if isinstance(item, Mapping)
                and cast(Mapping[str, object], item).get("external_transaction_id")
            }
            for transaction in broker.transactions:
                if (
                    transaction.transaction_type in {"ORDER_FILL", "TRADE_OPEN"}
                    and transaction.external_order_id
                    and transaction.external_order_id in local_order_external
                    and transaction.external_id not in fill_ids
                ):
                    return "MISSED_FILL_REQUIRES_REPAIR"
        return None

    @staticmethod
    def _required(reason: str) -> ReconciliationResult:
        return ReconciliationResult(
            ReconciliationOutcome.RECONCILIATION_REQUIRED,
            {"reason": reason},
            reason=reason,
        )


def session_policy_is_pinned(provenance: Mapping[str, object]) -> bool:
    """Return true only when official session-policy provenance is complete."""

    value = provenance.get("session_policy_provenance")
    if not isinstance(value, Mapping):
        return False
    values = cast(Mapping[str, object], value)
    required = ("source_url", "title", "retrieved_at", "effective_interval", "timezone")
    return all(
        isinstance(values.get(key), str)
        and bool(values[key])
        and "OANDA_DOC_PENDING" not in str(values[key])
        for key in required
    )


class ChronologicalDataProcessor:
    """Process completed M15 bars once and keep M1 execution separate."""

    def __init__(
        self,
        processor: BarProcessor,
        *,
        frontier: CompletedM15Frontier | None = None,
        execution_processor: ExecutionProcessor | None = None,
    ) -> None:
        self.processor = processor
        self.frontier = frontier or CompletedM15Frontier()
        self.execution_processor = execution_processor

    def process(
        self, deployment: RuntimeDeployment, cycle: RuntimeCycle, now: datetime
    ) -> int:
        if (cycle.warmup_m15 or cycle.completed_m15) and cycle.as_of is None:
            raise RuntimeErrorBase("analytical data cycle has no observation time")
        if cycle.as_of is not None and cycle.as_of > now:
            raise RuntimeErrorBase("data cycle is ahead of runtime clock")
        as_of = cycle.as_of or now

        self._validate_warmup(cycle.warmup_m15, as_of)
        accepted: list[tuple[Bar, CompletedM15Frontier]] = []
        candidate_frontier = self.frontier
        previous_input_end: datetime | None = None
        for bar in cycle.completed_m15:
            if previous_input_end is not None and bar.end_time < previous_input_end:
                raise LiveDataError("out-of-order completed M15 input")
            previous_input_end = bar.end_time
            next_frontier = candidate_frontier.accept(bar, as_of)
            if next_frontier is candidate_frontier:
                continue
            accepted.append((bar, next_frontier))
            candidate_frontier = next_frontier

        if cycle.warmup_m15:
            seed = getattr(self.processor, "seed_historical_context", None)
            if not callable(seed):
                raise RuntimeErrorBase("Strategy processor has no warm-up seed path")
            cast(HistoricalContextSeeder, self.processor).seed_historical_context(
                cycle.warmup_m15,
                as_of=as_of,
                durable_frontier=self.frontier.last_completed_end,
            )

        count = 0
        for bar, next_frontier in accepted:
            self.processor.process_completed_bar(
                deployment, bar, allow_entries=not cycle.catch_up
            )
            self.frontier = next_frontier
            count += 1
        if self.execution_processor is not None:
            for observation in sorted(
                cycle.execution_m1, key=lambda item: item.start_time
            ):
                self.execution_processor(deployment, observation, not cycle.catch_up)
        return count

    @staticmethod
    def _validate_warmup(bars: tuple[Bar, ...], as_of: datetime) -> None:
        previous_end: datetime | None = None
        fingerprints: dict[datetime, str] = {}
        for bar in bars:
            validate_completed_native_m15(bar, as_of)
            fingerprint = analytical_bar_fingerprint(bar)
            existing = fingerprints.get(bar.end_time)
            if existing is not None:
                if existing != fingerprint:
                    raise LiveDataError("conflicting duplicate warm-up M15 bar")
                continue
            if previous_end is not None and bar.end_time <= previous_end:
                raise LiveDataError("warm-up M15 bars must be chronological")
            if previous_end is not None and bar.end_time != previous_end + timedelta(
                minutes=15
            ):
                raise LiveDataError("warm-up M15 bars must be contiguous")
            fingerprints[bar.end_time] = fingerprint
            previous_end = bar.end_time


class RuntimeCoordinator:
    """Single-process owner of PAPER lifecycle and read-only reconciliation."""

    def __init__(
        self,
        store: RuntimeStore,
        reconciler: Reconciler,
        *,
        owner_id: str,
        acquire: Callable[[UUID], RuntimeLease | None],
        clock: Clock = utc_now,
        readiness: Callable[
            [RuntimeDeployment, ReconciliationResult, datetime], RuntimeReadiness
        ]
        | None = None,
        data_source: RuntimeDataSource | None = None,
        data_processors: Mapping[UUID, ChronologicalDataProcessor] | None = None,
        data_processor_factory: Callable[
            [RuntimeDeployment], ChronologicalDataProcessor
        ]
        | None = None,
        restore_runtime: Callable[
            [RuntimeDeployment, datetime], ChronologicalDataProcessor
        ]
        | None = None,
    ) -> None:
        if not owner_id or len(owner_id) > 120:
            raise ValueError("owner_id must be a bounded non-empty value")
        self.store = store
        self.reconciler = reconciler
        self.owner_id = owner_id
        self.acquire = acquire
        self.clock = clock
        self.readiness = readiness or self._default_readiness
        self.data_source = data_source
        self.data_processors = dict(data_processors or {})
        self.data_processor_factory = data_processor_factory
        self.restore_runtime = restore_runtime
        self._leases: dict[UUID, RuntimeLease] = {}
        self._ownership_proven: set[UUID] = set()
        self._explicit_controls: set[UUID] = set()
        self._stopping = False

    def command(
        self, deployment_id: UUID, command: RuntimeCommand
    ) -> RuntimeDeployment:
        """Persist desired state; no broker or execution request is made."""

        if type(command) is not RuntimeCommand:
            raise ValueError("invalid runtime command")
        if command is RuntimeCommand.RECONCILE:
            return self.reconcile(deployment_id, "MANUAL_REQUEST")
        desired = {
            RuntimeCommand.START: "RUNNING",
            RuntimeCommand.RESUME: "RUNNING",
            RuntimeCommand.PAUSE: "PAUSED",
            RuntimeCommand.STOP: "STOPPED",
            RuntimeCommand.ARCHIVE: "ARCHIVED",
        }.get(command)
        if desired is None:
            return self.store.get_deployment(deployment_id) or self._missing(
                deployment_id
            )
        row = self.store.request_state(deployment_id, desired)
        self._explicit_controls.add(deployment_id)
        return row

    def startup(self) -> tuple[RuntimeDeployment, ...]:
        self._stopping = False
        return self.reconcile_desired(startup=True)

    def reconcile_desired(
        self, *, startup: bool = False
    ) -> tuple[RuntimeDeployment, ...]:
        results: list[RuntimeDeployment] = []
        for deployment in self.store.eligible_deployments():
            if deployment.desired_state == "RUNNING":
                if (
                    deployment.actual_state
                    in {
                        ActualState.FAILED.value,
                        ActualState.RECONCILIATION_REQUIRED.value,
                    }
                    and deployment.id not in self._explicit_controls
                ):
                    continue
                results.append(
                    self._ensure_running(
                        deployment, "RUNTIME_START" if startup else "DESIRED_STATE"
                    )
                )
            elif deployment.desired_state == "PAUSED":
                results.append(self._ensure_paused(deployment, startup))
            elif deployment.desired_state == "STOPPED":
                results.append(self._ensure_stopped(deployment))
            elif deployment.desired_state == "ARCHIVED":
                results.append(self._archive(deployment))
        return tuple(results)

    def reconcile(
        self, deployment_id: UUID, trigger: str = "MANUAL_REQUEST"
    ) -> RuntimeDeployment:
        deployment = self.store.get_deployment(deployment_id)
        if deployment is None:
            return self._missing(deployment_id)
        if deployment.id not in self._leases and not self._acquire(deployment):
            return self.store.set_actual_state(
                deployment.id,
                ActualState.RECONCILIATION_REQUIRED.value,
                "Deployment runtime ownership is unavailable",
            )
        if not self._heartbeat(deployment, "RECONCILING"):
            return self.store.get_deployment(deployment.id) or deployment
        result = self._reconcile(deployment, trigger)
        if not self._reconciliation_allows_runtime(result):
            return self.store.set_actual_state(
                deployment.id,
                ActualState.RECONCILIATION_REQUIRED.value,
                self._reconciliation_block_reason(result),
            )
        return self.store.get_deployment(deployment.id) or deployment

    def reconnect(self) -> tuple[RuntimeDeployment, ...]:
        """Reconnect is a block-and-reconcile operation, never an auto-resume."""

        for deployment_id, lease in tuple(self._leases.items()):
            _ = lease
            deployment = self.store.get_deployment(deployment_id)
            if deployment is not None:
                result = self._reconcile(deployment, "BROKER_RECONNECT")
                if not self._reconciliation_allows_runtime(result):
                    self.store.set_actual_state(
                        deployment_id,
                        ActualState.RECONCILIATION_REQUIRED.value,
                        self._reconciliation_block_reason(result),
                    )
        return self.reconcile_desired()

    def cycle(self) -> tuple[RuntimeDeployment, ...]:
        """Apply commands once; callers may schedule this with ordinary polling."""

        if self._stopping:
            return ()
        results = self.reconcile_desired()
        if self.data_source is None:
            return results
        now = self.clock()
        for deployment in results:
            if deployment.actual_state != ActualState.RUNNING.value:
                continue
            if deployment.id not in self._ownership_proven or not self._heartbeat(
                deployment, "HEALTHY"
            ):
                continue
            processor = self.data_processors.get(deployment.id)
            if processor is None and self.data_processor_factory is not None:
                try:
                    processor = self.data_processor_factory(deployment)
                    self.data_processors[deployment.id] = processor
                except Exception as error:
                    self._block(
                        deployment.id,
                        f"Runtime data composition unavailable: {type(error).__name__}",
                    )
                    continue
            if processor is None:
                self._block(deployment.id, "Runtime data processor is unavailable")
                continue
            try:
                cycle = self.data_source.poll(deployment, now)
                if not self._heartbeat(deployment, "HEALTHY"):
                    continue
                processor.process(deployment, cycle, now)
            except Exception as error:
                self._block(
                    deployment.id, f"Live data is unavailable: {type(error).__name__}"
                )
        return results

    def shutdown(self) -> None:
        self._stopping = True
        for deployment_id, lease in tuple(self._leases.items()):
            deployment = self.store.get_deployment(deployment_id)
            if deployment is not None:
                self.store.heartbeat(
                    deployment_id,
                    self.owner_id,
                    lock_held=True,
                    db_connected=True,
                    health_status="STOPPING",
                    details={"new_exposure": False},
                )
            lease.release()
            if deployment is not None:
                self.store.heartbeat(
                    deployment_id,
                    self.owner_id,
                    lock_held=False,
                    db_connected=True,
                    health_status="STOPPED",
                    details={"new_exposure": False},
                )
            del self._leases[deployment_id]
            self._ownership_proven.discard(deployment_id)

    def _ensure_running(
        self, deployment: RuntimeDeployment, trigger: str
    ) -> RuntimeDeployment:
        if (
            deployment.actual_state == ActualState.RUNNING.value
            and deployment.id in self._leases
            and deployment.id not in self._explicit_controls
            and trigger == "DESIRED_STATE"
        ):
            if self._heartbeat(deployment, "HEALTHY"):
                return deployment
            return self.store.get_deployment(deployment.id) or deployment
        if not self._acquire(deployment):
            return self.store.set_actual_state(
                deployment.id,
                ActualState.FAILED.value,
                "Deployment runtime ownership is unavailable",
            )
        self.store.set_actual_state(deployment.id, ActualState.STARTING.value)
        if not self._heartbeat(deployment, "STARTING"):
            return self.store.get_deployment(deployment.id) or deployment
        result = self._reconcile(deployment, trigger)
        if not self._reconciliation_allows_runtime(result):
            return self.store.set_actual_state(
                deployment.id,
                ActualState.RECONCILIATION_REQUIRED.value,
                self._reconciliation_block_reason(result),
            )
        if not self._heartbeat(deployment, "RESTORING"):
            return self.store.get_deployment(deployment.id) or deployment
        try:
            if self.restore_runtime is not None:
                self.data_processors[deployment.id] = self.restore_runtime(
                    deployment, self.clock()
                )
            elif (
                self.data_source is not None
                and deployment.id not in self.data_processors
            ):
                raise RuntimeErrorBase("Strategy restoration seam is unavailable")
        except Exception as error:
            return self.store.set_actual_state(
                deployment.id,
                ActualState.FAILED.value,
                f"Strategy restoration failed: {type(error).__name__}",
            )
        if not self._heartbeat(deployment, "STARTING"):
            return self.store.get_deployment(deployment.id) or deployment
        gates = self.readiness(deployment, result, self.clock())
        if not gates.passed:
            return self.store.set_actual_state(
                deployment.id,
                ActualState.FAILED.value,
                gates.reason or "Runtime readiness gates did not pass",
            )
        running = self.store.set_actual_state(
            deployment.id, ActualState.RUNNING.value
        )
        self._explicit_controls.discard(deployment.id)
        if not self._heartbeat(running, "HEALTHY"):
            return self.store.get_deployment(deployment.id) or running
        return running

    def _ensure_paused(
        self, deployment: RuntimeDeployment, startup: bool
    ) -> RuntimeDeployment:
        if deployment.actual_state == ActualState.PAUSED.value:
            self._heartbeat(deployment, "PAUSED")
            return deployment
        if startup or deployment.actual_state in {
            ActualState.DRAFT.value,
            ActualState.STOPPED.value,
        }:
            if not self._acquire(deployment):
                return self.store.set_actual_state(
                    deployment.id,
                    ActualState.FAILED.value,
                    "Deployment runtime ownership is unavailable",
                )
            self.store.set_actual_state(deployment.id, ActualState.STARTING.value)
            if not self._heartbeat(deployment, "STARTING"):
                return self.store.get_deployment(deployment.id) or deployment
            result = self._reconcile(deployment, "DEPLOYMENT_START")
            if not self._reconciliation_allows_runtime(result):
                return self.store.set_actual_state(
                    deployment.id,
                    ActualState.RECONCILIATION_REQUIRED.value,
                    self._reconciliation_block_reason(result),
                )
        return self.store.set_actual_state(deployment.id, ActualState.PAUSED.value)

    def _ensure_stopped(self, deployment: RuntimeDeployment) -> RuntimeDeployment:
        if deployment.id not in self._leases and not self._acquire(deployment):
            return self.store.set_actual_state(
                deployment.id,
                ActualState.RECONCILIATION_REQUIRED.value,
                "Deployment runtime ownership is unavailable",
            )
        if not self._heartbeat(deployment, "RECONCILING"):
            return self.store.get_deployment(deployment.id) or deployment
        result = self._reconcile(deployment, "DEPLOYMENT_STOP")
        if not self._reconciliation_allows_runtime(result):
            return self.store.set_actual_state(
                deployment.id,
                ActualState.RECONCILIATION_REQUIRED.value,
                self._reconciliation_block_reason(result),
            )
        if result.broker is not None and result.broker.has_open_position:
            return self.store.set_actual_state(
                deployment.id,
                ActualState.RECONCILIATION_REQUIRED.value,
                "STOP is blocked while broker exposure is open",
            )
        stopped = self.store.set_actual_state(deployment.id, ActualState.STOPPED.value)
        self._release(deployment.id)
        return stopped

    def _archive(self, deployment: RuntimeDeployment) -> RuntimeDeployment:
        if deployment.id in self._leases:
            stopped = self._ensure_stopped(deployment)
            if stopped.actual_state != ActualState.STOPPED.value:
                return stopped
        return self.store.set_actual_state(deployment.id, ActualState.ARCHIVED.value)

    def _acquire(self, deployment: RuntimeDeployment) -> bool:
        if deployment.id in self._leases:
            return True
        lease = self.acquire(deployment.id)
        if lease is None:
            return False
        self._leases[deployment.id] = lease
        self._ownership_proven.discard(deployment.id)
        return True

    def _release(self, deployment_id: UUID) -> None:
        lease = self._leases.pop(deployment_id, None)
        if lease is not None:
            lease.release()
        self._ownership_proven.discard(deployment_id)

    def _heartbeat(self, deployment: RuntimeDeployment, health: str) -> bool:
        try:
            lease = self._leases.get(deployment.id)
            if lease is not None:
                probe = getattr(lease, "is_held", None)
                if callable(probe) and not probe():
                    raise RuntimeErrorBase("Deployment advisory lock is not held")
            self.store.heartbeat(
                deployment.id,
                self.owner_id,
                lock_held=deployment.id in self._leases,
                db_connected=True,
                health_status=health,
                details={"actual_state": deployment.actual_state},
            )
            if deployment.id not in self._leases and health not in {
                "PAUSED",
                "STOPPED",
            }:
                raise RuntimeErrorBase("Deployment lock ownership is not proven")
            self._ownership_proven.add(deployment.id)
            return True
        except Exception:
            self._ownership_proven.discard(deployment.id)
            self._block(
                deployment.id,
                "Runtime database connectivity or lock ownership is unavailable",
            )
            return False

    def _block(self, deployment_id: UUID, reason: str) -> None:
        """Best-effort durable block; stale RUNNING is never returned as proof."""

        self._ownership_proven.discard(deployment_id)
        try:
            self.store.set_actual_state(
                deployment_id, ActualState.RECONCILIATION_REQUIRED.value, reason
            )
        except Exception:
            # If the database is down, the in-memory ownership proof remains
            # false and cycle() stops before data or execution processing.
            return

    @staticmethod
    def _reconciliation_allows_runtime(result: ReconciliationResult) -> bool:
        return (
            result.outcome is not ReconciliationOutcome.RECONCILIATION_REQUIRED
            and result.durable_gate_proven
            and result.broker is not None
        )

    @staticmethod
    def _reconciliation_block_reason(result: ReconciliationResult) -> str:
        if result.reason:
            return result.reason
        if result.outcome is ReconciliationOutcome.RECONCILIATION_REQUIRED:
            return "Broker reconciliation is required"
        return "Durable reconciliation gate is not proven"

    def _reconcile(
        self, deployment: RuntimeDeployment, trigger: str
    ) -> ReconciliationResult:
        started = self.clock()
        try:
            result = self.reconciler.reconcile(deployment, trigger, started)
        except Exception:
            result = ReconciliationResult(
                ReconciliationOutcome.RECONCILIATION_REQUIRED,
                {"reason": "RECONCILIATION_FAILED"},
                reason="Reconciliation failed",
            )
        finished = self.clock()
        self.store.record_reconciliation(
            deployment.id,
            trigger=trigger,
            outcome=result.outcome,
            started_at=started,
            finished_at=finished,
            summary=result.summary,
            broker=result.broker,
        )
        return result

    def _default_readiness(
        self,
        deployment: RuntimeDeployment, result: ReconciliationResult, now: datetime
    ) -> RuntimeReadiness:
        broker = result.broker
        if broker is None:
            return RuntimeReadiness(reason="Broker facts are unavailable")
        policy = session_policy_is_pinned(deployment.execution_provenance)
        capabilities = all(
            broker.instrument.supports(value)
            for value in ("MARKET", "STOP_LOSS", "TAKE_PROFIT", "LONG", "SHORT")
        )
        restored = deployment.id in self.data_processors
        return RuntimeReadiness(
            capabilities_valid=capabilities,
            session_policy_valid=policy,
            state_valid=restored,
            warmup_valid=restored,
            data_fresh=broker.quote.is_fresh(now, timedelta(minutes=2)),
            protection_valid=broker.protection_verified,
            reason=(
                "Strategy state restoration and warm-up gates did not pass"
                if policy and capabilities and not restored
                else "Session-policy provenance or broker capabilities are incomplete"
            ),
        )

    @staticmethod
    def _missing(deployment_id: UUID) -> RuntimeDeployment:
        raise RuntimeErrorBase(f"Deployment does not exist: {deployment_id}")


__all__ = [
    "ActualState",
    "BarProcessor",
    "BrokerRead",
    "ChronologicalDataProcessor",
    "ExecutionProcessor",
    "ReadOnlyReconciler",
    "ReconciliationOutcome",
    "ReconciliationResult",
    "RuntimeCommand",
    "RuntimeCoordinator",
    "RuntimeCycle",
    "RuntimeDataSource",
    "RuntimeDeployment",
    "RuntimeErrorBase",
    "RuntimeLease",
    "RuntimeReadiness",
    "RuntimeStore",
    "session_policy_is_pinned",
]
