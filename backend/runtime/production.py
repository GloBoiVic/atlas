"""Concrete PAPER runtime composition and its explicit capital-action gate."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol, cast
from uuid import UUID

from backend.domain.broker import (
    AccountIdentity,
    AccountSnapshot,
    ExecutableQuote,
    VenueInstrumentFacts,
)
from backend.domain.market_data import Bar, Instrument, Provider
from backend.domain.strategy import (
    MarketSpecification,
    StrategyContext,
    StrategyEvaluation,
    StrategyParameterSet,
    StrategyStateEnvelope,
    StrategyVersion,
    ValidatedParameterPayload,
)
from backend.domain.trading import FinancialPositionState
from backend.execution.contract import Order
from backend.integrations.oanda.execution import (
    OandaExecutionAdapter,
    OandaExecutionResult,
    OandaExecutionTransport,
    OandaOrderStatus,
    ProtectionState,
    target_from_fill,
)
from backend.integrations.oanda.source import OandaHistoricalBarSource
from backend.market_data.live import (
    CompletedM15Frontier,
    LiveDataError,
    SparseM1ExecutionObservation,
    analytical_bar_fingerprint,
    evaluate_pending_entry,
    pair_sparse_m1_bars,
    validate_completed_native_m15,
)
from backend.risk import PaperRiskConfig, PaperRiskService, RiskDecision
from backend.risk import TradeIntent as RiskTradeIntent
from backend.strategies.contract import Strategy, evaluate_strategy
from backend.strategies.registry import StrategyRegistry

from .coordinator import (
    BrokerRead,
    BrokerReader,
    ChronologicalDataProcessor,
    RuntimeCycle,
    RuntimeDataSource,
    RuntimeDeployment,
)


class PaperRuntimeStore(Protocol):
    def strategy_runtime_inputs(
        self, deployment_id: UUID
    ) -> tuple[StrategyVersion, ValidatedParameterPayload, StrategyStateEnvelope]: ...

    def persist_strategy_state(
        self,
        deployment_id: UUID,
        strategy_version_id: UUID,
        state: StrategyStateEnvelope,
        analytical_bar_fingerprint: str,
    ) -> None: ...

    def persist_strategy_evaluation(
        self,
        deployment_id: UUID,
        strategy_version_id: UUID,
        state: StrategyStateEnvelope,
        evaluation: StrategyEvaluation,
        analytical_bar_fingerprint: str,
    ) -> None: ...

    def completed_m15_frontier(
        self, deployment_id: UUID
    ) -> CompletedM15Frontier: ...

    def reconciliation_facts(self, deployment_id: UUID) -> Mapping[str, object]: ...

    def validate_strategy_continuity(
        self, deployment_id: UUID, state: StrategyStateEnvelope
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class PendingPaperEntry:
    """The persisted handoff projected into the Risk boundary."""

    intent_id: UUID
    intent: RiskTradeIntent
    strategy_version_id: UUID


@dataclass(frozen=True, slots=True)
class PendingOrderResolution:
    """Result of the database-idempotent PAPER ENTRY Order fence."""

    order: Order
    created: bool
    current_status: str


class PaperAuthorizationStore(PaperRuntimeStore, Protocol):
    def pending_paper_entry(self, deployment_id: UUID) -> PendingPaperEntry | None: ...

    def paper_risk_config(self, deployment_id: UUID) -> PaperRiskConfig: ...

    def persist_risk_decision(
        self, intent_id: UUID, decision: RiskDecision, evaluated_at: datetime
    ) -> UUID: ...

    def entry_order_resolution(
        self, deployment_id: UUID, intent_id: UUID
    ) -> PendingOrderResolution | None: ...

    def create_pending_order(
        self,
        deployment: RuntimeDeployment,
        pending: PendingPaperEntry,
        decision: RiskDecision,
        persisted_decision_id: UUID,
    ) -> PendingOrderResolution: ...

    def apply_execution_result(
        self, deployment_id: UUID, result: OandaExecutionResult
    ) -> None: ...

    def mark_entry_rejected(self, intent_id: UUID, reason: str) -> None: ...

    def record_protection(
        self, deployment_id: UUID, order_id: UUID, state: ProtectionState
    ) -> None: ...

    def record_protection_failure(self, deployment_id: UUID, reason: str) -> None: ...


class OandaLiveDataSource(RuntimeDataSource):
    """Poll native completed M15 and sparse completed M1 data using GET only."""

    def __init__(
        self,
        source: OandaHistoricalBarSource,
        *,
        warmup_bars: int = 100,
        execution_lookback_minutes: int = 10,
    ) -> None:
        if warmup_bars < 1 or execution_lookback_minutes < 1:
            raise ValueError("live data lookbacks must be positive")
        self.source = source
        self.warmup_bars = warmup_bars
        self.execution_lookback_minutes = execution_lookback_minutes

    def poll(self, deployment: RuntimeDeployment, now: datetime) -> RuntimeCycle:
        _ = deployment
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("live runtime clock must be timezone-aware UTC")
        observed_at = now.astimezone(UTC)
        m15_end = observed_at.replace(
            minute=(observed_at.minute // 15) * 15,
            second=0,
            microsecond=0,
        )
        m15_start = m15_end - timedelta(minutes=15)
        m15 = self.source.fetch_completed_native_m15(
            m15_start, m15_end, as_of=observed_at
        )
        if m15.incomplete:
            raise LiveDataError("OANDA returned an incomplete analytical M15 candle")
        m1_end = observed_at.replace(second=0, microsecond=0)
        m1_start = m1_end - timedelta(minutes=self.execution_lookback_minutes)
        execution = self.source.fetch_completed_execution_m1(
            m1_start, m1_end, as_of=observed_at
        )
        return RuntimeCycle(
            completed_m15=m15.bars,
            execution_m1=pair_sparse_m1_bars(execution.bars),
            as_of=observed_at,
        )

    def restore(
        self,
        deployment: RuntimeDeployment,
        now: datetime,
        durable_frontier: datetime,
    ) -> RuntimeCycle:
        """Load one restart snapshot: context through the frontier, then catch-up."""

        _ = deployment
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("live runtime clock must be timezone-aware UTC")
        if (
            durable_frontier.tzinfo is None
            or durable_frontier.utcoffset() != timedelta(0)
        ):
            raise ValueError("durable analytical frontier must be timezone-aware UTC")
        observed_at = now.astimezone(UTC)
        frontier = durable_frontier.astimezone(UTC)
        if frontier > observed_at:
            raise LiveDataError("durable analytical frontier is ahead of runtime clock")
        completed_end = observed_at.replace(
            minute=(observed_at.minute // 15) * 15,
            second=0,
            microsecond=0,
        )
        # Seven days is the smallest bounded window that still contains 100
        # received M15 bars across the normal FX weekend closure. Catch-up may
        # extend farther when the durable frontier is older.
        start = frontier - timedelta(days=7)
        result = self.source.fetch_completed_native_m15(
            start, completed_end, as_of=observed_at
        )
        if result.incomplete:
            raise LiveDataError("OANDA returned an incomplete analytical M15 candle")
        ordered = tuple(sorted(result.bars, key=lambda bar: bar.end_time))
        context = tuple(bar for bar in ordered if bar.end_time <= frontier)
        if len(context) < self.warmup_bars:
            raise LiveDataError("PAPER Strategy warm-up context is incomplete")
        warmup = context[-self.warmup_bars :]
        if warmup[-1].end_time != frontier:
            raise LiveDataError(
                "PAPER Strategy warm-up context does not reach durable frontier"
            )
        catch_up = tuple(bar for bar in ordered if bar.end_time > frontier)
        return RuntimeCycle(
            warmup_m15=warmup,
            completed_m15=catch_up,
            as_of=observed_at,
            catch_up=True,
        )


class StrategyBarProcessor:
    """Evaluate the registered Strategy only on a completed M15 frontier."""

    def __init__(
        self,
        strategy: Strategy,
        parameters: StrategyParameterSet | ValidatedParameterPayload,
        state: StrategyStateEnvelope,
        market: MarketSpecification,
        *,
        persist_state: Callable[[StrategyStateEnvelope, str], None] | None = None,
        persist_evaluation: Callable[
            [StrategyStateEnvelope, StrategyEvaluation, str], None
        ]
        | None = None,
        on_evaluation: Callable[[StrategyEvaluation], None] | None = None,
    ) -> None:
        self.strategy = strategy
        self.parameters = parameters
        self.state = state
        self.market = market
        self.persist_state = persist_state
        self.persist_evaluation = persist_evaluation
        self.on_evaluation = on_evaluation
        self.bars: list[Bar] = []
        self.pending_entry = state.pending_entry

    def seed_historical_context(
        self,
        bars: tuple[Bar, ...],
        *,
        as_of: datetime,
        durable_frontier: datetime | None,
    ) -> None:
        """Restore validated analytical context without evaluating Strategy."""

        required = self.strategy.definition.required_historical_context_bars
        if len(bars) < required:
            raise ValueError("PAPER Strategy warm-up context is incomplete")
        previous_end: datetime | None = None
        seeded: list[Bar] = []
        for bar in bars:
            validate_completed_native_m15(bar, as_of)
            if durable_frontier is not None and bar.end_time > durable_frontier:
                raise ValueError("warm-up bar is ahead of the durable frontier")
            if previous_end is not None and bar.end_time <= previous_end:
                raise ValueError("PAPER Strategy warm-up context is not chronological")
            seeded.append(bar)
            previous_end = bar.end_time
        self.bars = seeded[-required:]

    def process_completed_bar(
        self, deployment: RuntimeDeployment, bar: Bar, *, allow_entries: bool
    ) -> None:
        _ = deployment
        if bar.instrument is not Instrument.EUR_USD:
            raise ValueError("PAPER Strategy received an unsupported instrument")
        required = self.strategy.definition.required_historical_context_bars
        context_bars = [*self.bars, bar]
        if len(context_bars) < required:
            raise ValueError(
                "PAPER Strategy evaluation requires seeded warm-up context"
            )
        context = StrategyContext(
            evaluation_time=bar.end_time,
            instrument=Instrument.EUR_USD,
            bars=tuple(context_bars[-required:]),
            market=self.market,
            exposure_allowed=allow_entries,
        )
        result = evaluate_strategy(self.strategy, context, self.parameters, self.state)
        if type(result.next_state) is not StrategyStateEnvelope:
            raise ValueError("PAPER Strategy returned an invalid state envelope")
        if result.next_state.last_evaluated_bar_end != bar.end_time:
            raise ValueError("PAPER Strategy state does not match analytical frontier")
        fingerprint = analytical_bar_fingerprint(bar)
        if allow_entries and self.persist_evaluation is not None:
            self.persist_evaluation(result.next_state, result, fingerprint)
        elif self.persist_state is not None:
            self.persist_state(result.next_state, fingerprint)
        self.state = result.next_state
        self.pending_entry = result.next_state.pending_entry
        self.bars = context_bars[-required:]
        if allow_entries and self.on_evaluation is not None:
            self.on_evaluation(result)


class PaperEntryProcessor:
    """Gate post-frontier M1 observations without a hidden submit path."""

    def __init__(
        self,
        strategy_processor: StrategyBarProcessor,
        *,
        on_eligible: Callable[
            [RuntimeDeployment, SparseM1ExecutionObservation], None
        ]
        | None = None,
    ) -> None:
        self.strategy_processor = strategy_processor
        self.on_eligible = on_eligible

    def __call__(
        self,
        deployment: RuntimeDeployment,
        observation: SparseM1ExecutionObservation,
        allow_entries: bool,
    ) -> None:
        if not allow_entries or self.strategy_processor.pending_entry is None:
            return
        evaluation = evaluate_pending_entry(
            self.strategy_processor.pending_entry, observation
        )
        if not evaluation.eligible:
            if evaluation.status.value == "EXPIRED":
                self.strategy_processor.pending_entry = None
            return
        if self.on_eligible is None:
            raise RuntimeError(
                "PAPER entry authorization is not installed; exposure is blocked"
            )
        self.on_eligible(deployment, observation)


class PaperEntryAuthorizer:
    """Run the only production Strategy → Risk → execution authorization path.

    The callback is deliberately inert unless a caller supplies both an
    explicit capital-action approval and a transport.  Construction, startup,
    reconciliation, and non-capital validation therefore cannot submit an
    order.  The network call is made only after the PENDING_SUBMISSION row has
    been committed by the store.
    """

    def __init__(
        self,
        *,
        store: PaperAuthorizationStore,
        broker_reader: Callable[[RuntimeDeployment, datetime], BrokerRead],
        risk: PaperRiskService,
        execution: OandaExecutionAdapter,
        transport: OandaExecutionTransport | None,
        capital_actions_enabled: bool,
        clock: Callable[[], datetime],
        expected_account: AccountIdentity,
    ) -> None:
        self.store = store
        self.broker_reader = broker_reader
        self.risk = risk
        self.execution = execution
        self.transport = transport
        self.capital_actions_enabled = capital_actions_enabled
        self.clock = clock
        self.expected_account = expected_account
        self._attempted_intents: set[UUID] = set()

    def __call__(
        self, deployment: RuntimeDeployment, _observation: SparseM1ExecutionObservation
    ) -> None:
        # This is the activation boundary.  It is intentionally checked before
        # reading or constructing any submit-capable provider request.
        if not self.capital_actions_enabled or self.transport is None:
            return
        pending = self.store.pending_paper_entry(deployment.id)
        if pending is None:
            raise RuntimeError("eligible entry has no persisted TradeIntent handoff")
        if (
            self.store.entry_order_resolution(deployment.id, pending.intent_id)
            is not None
        ):
            # Any existing ENTRY Order is authoritative lifecycle state.  It is
            # resolved by reconciliation, never by another authorization call.
            return
        # A submission outcome of UNKNOWN is not a retryable path.  Keep this
        # guard for the lifetime of the owner; restart/reacquisition goes
        # through broker reconciliation instead.
        if pending.intent_id in self._attempted_intents:
            return
        self._attempted_intents.add(pending.intent_id)
        now = self.clock().astimezone(UTC)
        before = self.broker_reader(deployment, now)
        self._validate_broker_read(before)
        config = self.store.paper_risk_config(deployment.id)
        position = self._local_position(deployment.id)
        pre_flight = self.risk.evaluate_pre_flight(
            pending.intent,
            deployment_state=deployment.actual_state,
            position=position,
            account=before.account,
            instrument=before.instrument,
            config=config,
            evaluated_at=now,
            pending_entry=False,
        )
        self.store.persist_risk_decision(pending.intent_id, pre_flight, now)
        if not pre_flight.approved:
            self.store.mark_entry_rejected(
                pending.intent_id,
                pre_flight.rejection.value
                if pre_flight.rejection
                else "RISK_REJECTED",
            )
            return

        # PRE_SUBMISSION is based on a second, post-decision broker read.  The
        # quote from PRE_FLIGHT is never reused as executable authorization.
        submitted_at = self.clock().astimezone(UTC)
        after = self.broker_reader(deployment, submitted_at)
        self._validate_broker_read(after)
        pre_submission = self.risk.evaluate_pre_submission(
            pending.intent,
            deployment_state=deployment.actual_state,
            position=self._local_position(deployment.id),
            account=after.account,
            instrument=after.instrument,
            config=config,
            quote=after.quote,
            evaluated_at=submitted_at,
        )
        persisted_decision_id = self.store.persist_risk_decision(
            pending.intent_id, pre_submission, submitted_at
        )
        if not pre_submission.approved:
            self.store.mark_entry_rejected(
                pending.intent_id,
                pre_submission.rejection.value
                if pre_submission.rejection
                else "RISK_REJECTED",
            )
            return
        resolution = self.store.create_pending_order(
            deployment,
            pending,
            pre_submission,
            persisted_decision_id,
        )
        if not resolution.created:
            return
        order = resolution.order
        result = self.execution.submit_entry(
            self.transport,
            account_id=deployment.account_id,
            order=order,
            # create_pending_order is the committed PENDING_SUBMISSION boundary.
            persist_pending=lambda: None,
        )
        self.store.apply_execution_result(deployment.id, result)
        if result.status is not OandaOrderStatus.FULL_FILLED:
            return
        if result.fill is None or not result.external_trade_ids:
            self.store.record_protection_failure(
                deployment.id, "FULL_FILL_PROTECTION_IDENTITY_UNAVAILABLE"
            )
            return
        stop = pre_submission.stop_price
        if stop is None:
            self.store.record_protection_failure(
                deployment.id, "APPROVED_STOP_UNAVAILABLE"
            )
            return
        target = target_from_fill(
            result.fill.execution_price,
            stop,
            pending.intent.direction.value if pending.intent.direction else "",
            pending.intent.target.multiple if pending.intent.target else Decimal("1.7"),
        )
        try:
            protection = self.execution.attach_target(
                self.transport,
                account_id=deployment.account_id,
                trade_id=result.external_trade_ids[0],
                target_price=target,
                units=result.fill.quantity,
                client_correlation_id=order.client_correlation_id or "",
            )
            confirmed = self.execution.confirm_protection(
                self.transport,
                account_id=deployment.account_id,
                trade_id=result.external_trade_ids[0],
                direction=(
                    pending.intent.direction.value
                    if pending.intent.direction
                    else ""
                ),
                quantity=result.fill.quantity,
                stop_price=stop,
                target_price=target,
            )
        except Exception as error:
            self.store.record_protection_failure(
                deployment.id, f"PROTECTION_{type(error).__name__.upper()}"
            )
            return
        if not confirmed.same_protection(protection):
            self.store.record_protection_failure(
                deployment.id, "PROTECTION_STATE_DRIFT"
            )
            return
        self.store.record_protection(deployment.id, order.id, confirmed)

    def _local_position(self, deployment_id: UUID) -> FinancialPositionState | None:
        facts = self.store.reconciliation_facts(deployment_id)
        raw = facts.get("position")
        if not isinstance(raw, Mapping):
            return None
        position = cast(Mapping[str, object], raw)
        state = position.get("state")
        if type(state) is not str:
            return None
        try:
            return FinancialPositionState(state)
        except ValueError:
            return None

    def _validate_broker_read(self, broker: BrokerRead) -> None:
        """Bind each authorization read independently to the Deployment account."""

        if type(broker) is not BrokerRead:
            raise ValueError("PAPER broker read is missing normalized identity")
        account = broker.account
        instrument = broker.instrument
        quote = broker.quote
        if (
            type(account) is not AccountSnapshot
            or type(account.identity) is not AccountIdentity
            or account.identity != self.expected_account
        ):
            raise ValueError("PAPER broker read does not match the selected account")
        if (
            account.identity.provider is not Provider.OANDA
            or account.identity.environment != "Practice"
            or account.identity.base_currency != "USD"
        ):
            raise ValueError("PAPER broker account facts are unsupported")
        if (
            type(instrument) is not VenueInstrumentFacts
            or instrument.venue_instrument.provider is not Provider.OANDA
            or instrument.venue_instrument.instrument is not Instrument.EUR_USD
            or instrument.venue_instrument.provider_symbol != "EUR_USD"
        ):
            raise ValueError("PAPER broker instrument facts are not OANDA EUR/USD")
        if (
            type(quote) is not ExecutableQuote
            or quote.instrument is not Instrument.EUR_USD
        ):
            raise ValueError("PAPER executable quote is not EUR/USD")


class ProductionPaperComposition:
    """Own the production PAPER seams without enabling capital actions."""

    def __init__(
        self,
        *,
        source: OandaHistoricalBarSource,
        registry: StrategyRegistry,
        store: PaperRuntimeStore,
        market: MarketSpecification,
        broker_reader: Callable[[RuntimeDeployment, datetime], BrokerRead]
        | BrokerReader
        | None = None,
        execution_transport: OandaExecutionTransport | None = None,
        capital_actions_enabled: bool = False,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.data_source = OandaLiveDataSource(source)
        self.registry = registry
        self.store = store
        self.market = market
        self.risk = PaperRiskService()
        self.execution = OandaExecutionAdapter()
        reader: Callable[[RuntimeDeployment, datetime], BrokerRead] | None
        if broker_reader is None:
            reader = None
        elif callable(broker_reader):
            reader = broker_reader
        else:
            reader = broker_reader.read
        self.broker_reader = reader
        self.execution_transport = execution_transport
        self.capital_actions_enabled = capital_actions_enabled
        self.clock = clock

    def processor_for(
        self, deployment: RuntimeDeployment
    ) -> ChronologicalDataProcessor:
        """Construct a processor from already-validated durable state."""

        inputs = self.store.strategy_runtime_inputs(deployment.id)
        version, parameters, state = inputs
        if type(state) is not StrategyStateEnvelope:
            raise ValueError("Deployment Strategy state is invalid")
        strategy = self.registry.implementation_for_version(version)
        definition = strategy.definition
        if (
            definition.state_schema_version != version.state_schema_version
            or definition.required_historical_context_bars
            != version.required_historical_context_bars
            or definition.primary_timeframe is not version.primary_timeframe
            or state.state_schema_version != version.state_schema_version
        ):
            raise ValueError("StrategyVersion and executable state schema disagree")
        self.store.validate_strategy_continuity(deployment.id, state)
        processor = StrategyBarProcessor(
            strategy,
            parameters,
            state,
            self.market,
            persist_state=lambda value, fingerprint: self.store.persist_strategy_state(  # type: ignore[attr-defined]
                deployment.id, version.id, value, fingerprint
            ),
        )
        persist_evaluation = getattr(self.store, "persist_strategy_evaluation", None)
        authorizer = None
        if self.broker_reader is not None:
            authorizer = PaperEntryAuthorizer(
                store=self.store,  # type: ignore[arg-type]
                broker_reader=cast(
                    Callable[[RuntimeDeployment, datetime], BrokerRead],
                    self.broker_reader,
                ),
                risk=self.risk,
                execution=self.execution,
                transport=self.execution_transport,
                capital_actions_enabled=self.capital_actions_enabled,
                clock=self.clock,
                expected_account=cast(AccountIdentity, deployment.trading_account),
            )
        if callable(persist_evaluation):
            def persist_evaluated(
                value: StrategyStateEnvelope,
                evaluation: StrategyEvaluation,
                fingerprint: str,
            ) -> None:
                cast(Callable[..., None], persist_evaluation)(
                    deployment.id, version.id, value, evaluation, fingerprint
                )

            processor.persist_evaluation = persist_evaluated
        entry_processor = PaperEntryProcessor(processor, on_eligible=authorizer)
        frontier = self.store.completed_m15_frontier(deployment.id)
        if frontier.last_completed_end != state.last_evaluated_bar_end:
            raise ValueError("Strategy state and durable analytical frontier disagree")

        return ChronologicalDataProcessor(
            processor,
            frontier=frontier,
            execution_processor=entry_processor,
        )

    def restore_for_startup(
        self, deployment: RuntimeDeployment, now: datetime
    ) -> ChronologicalDataProcessor:
        """Rebuild context and capital-inert catch-up before actual RUNNING."""

        processor = self.processor_for(deployment)
        frontier = processor.frontier.last_completed_end
        if frontier is None:
            raise ValueError("Deployment has no durable analytical frontier")
        cycle = self.data_source.restore(deployment, now, frontier)
        processor.process(deployment, cycle, now)
        strategy_processor = cast(StrategyBarProcessor, processor.processor)
        self.store.validate_strategy_continuity(
            deployment.id, strategy_processor.state
        )
        return processor


__all__ = [
    "OandaLiveDataSource",
    "PaperEntryProcessor",
    "PaperEntryAuthorizer",
    "PendingPaperEntry",
    "PendingOrderResolution",
    "ProductionPaperComposition",
    "StrategyBarProcessor",
]
