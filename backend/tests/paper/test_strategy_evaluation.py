from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from backend.domain import (
    Action,
    Bar,
    Direction,
    EntryPolicy,
    FinancialPositionState,
    Instrument,
    MarketSpecification,
    ParameterError,
    ParameterSchema,
    PositionState,
    PriceComponent,
    Rationale,
    StrategyContext,
    StrategyDecision,
    StrategyEvaluation,
    StrategyParameters,
    StrategyParameterSet,
    StrategyStateEnvelope,
    StrategyStatePayloadDocument,
    StrategyVersion,
    Timeframe,
    ValidatedParameterPayload,
)
from backend.market_data.session_calendar import (
    eligible_m15_windows,
    required_warmup_range,
)
from backend.paper.strategy_evaluation import (
    PaperStrategyEvaluationError,
    evaluate_current_paper_strategy,
)
from backend.strategies.contract import (
    Strategy,
    StrategyDefinition,
    evaluate_strategy,
    initial_strategy_state,
)
from backend.strategies.production import create_production_strategy_registry
from backend.strategies.registry import StrategyVersionUnavailableError

ROOT = Path(__file__).parents[3]
MARKET = MarketSpecification(Instrument.EUR_USD, Decimal("0.0001"))
NOW = datetime(2026, 1, 5, 10, 17, tzinfo=UTC)
VERSION_ID = UUID("11111111-1111-1111-1111-111111111111")
SESSION = cast(Session, object())


@dataclass(frozen=True)
class FetchResult:
    bars: tuple[Bar, ...]
    incomplete: tuple[object, ...] = ()


@dataclass
class RecordingSource:
    factory: Callable[[datetime, datetime], tuple[Bar, ...]]

    def __post_init__(self) -> None:
        self.calls: list[tuple[datetime, datetime]] = []

    def fetch_native_m15(self, start: datetime, end: datetime) -> FetchResult:
        self.calls.append((start, end))
        return FetchResult(self.factory(start, end))


class RecordingRepository:
    def __init__(self, rows: dict[UUID, object]) -> None:
        self.rows = rows
        self.calls: list[UUID] = []

    def get_version(self, _session: object, version_id: UUID) -> object | None:
        self.calls.append(version_id)
        return self.rows.get(version_id)


class RecordingRegistry:
    def __init__(self, implementation: Strategy) -> None:
        self.implementation = implementation
        self.versions: list[StrategyVersion] = []

    def implementation_for_version(self, version: StrategyVersion) -> Strategy:
        self.versions.append(version)
        return self.implementation


def bar(
    start: datetime,
    *,
    open_price: str = "1.1000",
    high: str = "1.1010",
    low: str = "1.0990",
    close: str = "1.1000",
) -> Bar:
    return Bar(
        Instrument.EUR_USD,
        Timeframe.M15,
        PriceComponent.MID,
        start,
        start + timedelta(minutes=15),
        Decimal(open_price),
        Decimal(high),
        Decimal(low),
        Decimal(close),
    )


def bars_for(start: datetime, end: datetime) -> tuple[Bar, ...]:
    return tuple(
        bar(window_start) for window_start, _ in eligible_m15_windows(start, end)
    )


def persisted_row(
    version_id: UUID,
    definition: StrategyDefinition,
    *,
    source_fingerprint: str = "a" * 64,
    parameter_schema: tuple[ParameterSchema, ...] | None = None,
    primary_timeframe: Timeframe | None = None,
    required_historical_context_bars: int | None = None,
    state_schema_version: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=version_id,
        strategy=SimpleNamespace(strategy_key=definition.strategy_key),
        version_number=1,
        source_fingerprint=source_fingerprint,
        implementation_key=definition.implementation_key,
        parameter_schema=[
            item.to_json()
            for item in (
                parameter_schema
                if parameter_schema is not None
                else definition.parameter_schema
            )
        ],
        primary_timeframe=(
            primary_timeframe
            if primary_timeframe is not None
            else definition.primary_timeframe
        ).value,
        required_historical_context_bars=(
            required_historical_context_bars
            if required_historical_context_bars is not None
            else definition.required_historical_context_bars
        ),
        state_schema_version=(
            state_schema_version
            if state_schema_version is not None
            else definition.state_schema_version
        ),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def explicit_parameters(
    definition: StrategyDefinition,
) -> dict[str, int | str | bool | None]:
    return {item.key: item.default for item in definition.parameter_schema}


class FixtureStrategy:
    definition = StrategyDefinition(
        "paper_fixture",
        "PAPER fixture",
        "A deterministic Strategy test double",
        (ParameterSchema("threshold", "Threshold", "integer", 1, False, 1, 3, "x"),),
        required_historical_context_bars=2,
        implementation_key="paper_fixture.v1",
    )

    def __init__(self) -> None:
        self.contexts: list[StrategyContext] = []

    @classmethod
    def initial_state(cls) -> StrategyStateEnvelope:
        return StrategyStateEnvelope(
            1,
            None,
            StrategyStatePayloadDocument.from_mapping("paper_fixture.v1", 1, {}),
        )

    @staticmethod
    def parse_parameters(_payload: ValidatedParameterPayload) -> StrategyParameterSet:
        return _payload

    def evaluate(
        self,
        context: StrategyContext,
        parameters: StrategyParameterSet,
        state: StrategyStateEnvelope,
    ) -> StrategyEvaluation:
        del parameters
        self.contexts.append(context)
        return StrategyEvaluation(
            StrategyDecision(Action.NO_ACTION, Rationale("FIXTURE")),
            state.advance_to(context.bars[-1].end_time, context.evaluation_time),
        )


def make_dependencies(
    implementation: FixtureStrategy | None = None,
    *,
    now: datetime = NOW,
    factory: Callable[[datetime, datetime], tuple[Bar, ...]] = bars_for,
) -> tuple[RecordingRepository, RecordingRegistry, RecordingSource]:
    implementation = implementation or FixtureStrategy()
    row = persisted_row(VERSION_ID, implementation.definition)
    repository = RecordingRepository({VERSION_ID: row})
    registry = RecordingRegistry(implementation)
    source = RecordingSource(factory)
    return repository, registry, source


def evaluate_fixture(
    *,
    state: StrategyStateEnvelope | None = None,
    financial_position_state: FinancialPositionState = FinancialPositionState.FLAT,
    parameter_values: dict[str, object] | None = None,
    implementation: FixtureStrategy | None = None,
    repository: RecordingRepository | None = None,
    registry: RecordingRegistry | None = None,
    source: RecordingSource | None = None,
    now: datetime = NOW,
) -> StrategyEvaluation:
    if repository is None or registry is None or source is None:
        repository, registry, source = make_dependencies(implementation, now=now)
    actual_implementation = registry.implementation
    return evaluate_current_paper_strategy(
        SESSION,
        strategy_version_id=VERSION_ID,
        parameter_values=parameter_values
        if parameter_values is not None
        else explicit_parameters(actual_implementation.definition),
        state=state,
        financial_position_state=financial_position_state,
        now=now,
        strategy_repository=repository,  # type: ignore[arg-type]
        strategy_registry=registry,  # type: ignore[arg-type]
        analytical_source=source,
        market_specification=MARKET,
    )


def test_exact_version_and_complete_parameters_are_used_without_defaults() -> None:
    implementation = FixtureStrategy()
    repository, registry, source = make_dependencies(implementation)

    result = evaluate_fixture(
        implementation=implementation,
        repository=repository,
        registry=registry,
        source=source,
        parameter_values={"threshold": 2},
    )

    assert type(result) is StrategyEvaluation
    assert repository.calls == [VERSION_ID]
    assert registry.versions[0].id == VERSION_ID
    assert len(source.calls) == 1
    assert len(implementation.contexts) == 3
    assert [context.evaluation_time for context in implementation.contexts] == [
        item.bars[-1].end_time for item in implementation.contexts
    ]
    assert [context.exposure_allowed for context in implementation.contexts] == [
        False,
        False,
        True,
    ]


@pytest.mark.parametrize(
    "parameter_values",
    ({}, {"threshold": 2, "unexpected": 1}, {"threshold": 4}),
)
def test_parameters_are_exact_and_invalid_values_fail_before_strategy(
    parameter_values: dict[str, object],
) -> None:
    implementation = FixtureStrategy()
    repository, registry, source = make_dependencies(implementation)

    with pytest.raises(ParameterError):
        evaluate_fixture(
            implementation=implementation,
            repository=repository,
            registry=registry,
            source=source,
            parameter_values=parameter_values,
        )

    assert implementation.contexts == []
    assert source.calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("parameter_schema", ()),
        ("primary_timeframe", Timeframe.M1),
        ("required_historical_context_bars", 3),
        ("state_schema_version", 2),
    ),
)
def test_persisted_local_metadata_mismatch_fails_before_source(
    field: str, value: object
) -> None:
    implementation = FixtureStrategy()
    row = persisted_row(
        VERSION_ID,
        implementation.definition,
        source_fingerprint=cast(Any, value)
        if field == "source_fingerprint"
        else "a" * 64,
        parameter_schema=cast(Any, value) if field == "parameter_schema" else None,
        primary_timeframe=cast(Any, value) if field == "primary_timeframe" else None,
        required_historical_context_bars=cast(Any, value)
        if field == "required_historical_context_bars"
        else None,
        state_schema_version=cast(Any, value)
        if field == "state_schema_version"
        else None,
    )
    repository = RecordingRepository({VERSION_ID: row})
    registry = RecordingRegistry(implementation)
    source = RecordingSource(bars_for)

    with pytest.raises(PaperStrategyEvaluationError, match=field):
        evaluate_fixture(
            implementation=implementation,
            repository=repository,
            registry=registry,
            source=source,
        )

    assert source.calls == []
    assert implementation.contexts == []


def test_initial_nonflat_bootstrap_fails_without_reading_or_evaluating() -> None:
    implementation = FixtureStrategy()
    repository, registry, source = make_dependencies(implementation)

    with pytest.raises(PaperStrategyEvaluationError, match="FLAT"):
        evaluate_fixture(
            implementation=implementation,
            repository=repository,
            registry=registry,
            source=source,
            financial_position_state=FinancialPositionState.LONG,
        )

    assert repository.calls == []
    assert source.calls == []
    assert implementation.contexts == []


@pytest.mark.parametrize(
    ("financial_state", "expected"),
    (
        (FinancialPositionState.FLAT, PositionState.FLAT),
        (FinancialPositionState.LONG, PositionState.LONG),
        (FinancialPositionState.SHORT, PositionState.SHORT),
    ),
)
def test_restored_state_translates_financial_position_explicitly(
    financial_state: FinancialPositionState, expected: PositionState
) -> None:
    implementation = FixtureStrategy()
    repository, registry, source = make_dependencies(implementation)
    prior = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
    state = StrategyStateEnvelope(
        1,
        prior,
        StrategyStatePayloadDocument.from_mapping("paper_fixture.v1", 1, {}),
    )

    evaluate_fixture(
        state=state,
        financial_position_state=financial_state,
        implementation=implementation,
        repository=repository,
        registry=registry,
        source=source,
    )

    assert implementation.contexts[-1].position is expected
    assert implementation.contexts[-1].exposure_allowed is True


def test_restored_prior_state_advances_once_without_historical_replay() -> None:
    implementation = FixtureStrategy()
    repository, registry, source = make_dependencies(implementation)
    state = StrategyStateEnvelope(
        1,
        datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
        StrategyStatePayloadDocument.from_mapping("paper_fixture.v1", 1, {}),
    )

    result = evaluate_fixture(
        state=state,
        implementation=implementation,
        repository=repository,
        registry=registry,
        source=source,
    )

    assert len(implementation.contexts) == 1
    assert implementation.contexts[0].bars[-1].end_time == datetime(
        2026, 1, 5, 10, 15, tzinfo=UTC
    )
    assert result.next_state.last_evaluated_bar_end == datetime(
        2026, 1, 5, 10, 15, tzinfo=UTC
    )


def test_same_frontier_preserves_duplicate_failure_and_does_not_call_strategy() -> None:
    implementation = FixtureStrategy()
    repository, registry, source = make_dependencies(implementation)
    state = StrategyStateEnvelope(
        1,
        datetime(2026, 1, 5, 10, 15, tzinfo=UTC),
        StrategyStatePayloadDocument.from_mapping("paper_fixture.v1", 1, {}),
    )

    from backend.strategies.contract import DuplicateBarEvaluationError

    with pytest.raises(DuplicateBarEvaluationError):
        evaluate_fixture(
            state=state,
            implementation=implementation,
            repository=repository,
            registry=registry,
            source=source,
        )

    assert implementation.contexts == []


def test_stale_state_and_unresolved_pending_entry_fail_before_strategy() -> None:
    implementation = FixtureStrategy()
    repository, registry, source = make_dependencies(implementation)
    stale = StrategyStateEnvelope(
        1,
        datetime(2026, 1, 5, 9, 45, tzinfo=UTC),
        StrategyStatePayloadDocument.from_mapping("paper_fixture.v1", 1, {}),
    )

    with pytest.raises(PaperStrategyEvaluationError, match="not caught up"):
        evaluate_fixture(
            state=stale,
            implementation=implementation,
            repository=repository,
            registry=registry,
            source=source,
        )
    assert implementation.contexts == []

    from backend.domain import PendingEntryHandoff

    pending = PendingEntryHandoff(
        EntryPolicy.PRICE_TRIGGERED,
        Direction.LONG,
        Decimal("1.1010"),
        PriceComponent.ASK,
        datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
        datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
        5,
    )
    state_with_pending = StrategyStateEnvelope(
        1,
        datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
        StrategyStatePayloadDocument.from_mapping("paper_fixture.v1", 1, {}),
        pending_entry=pending,
    )
    with pytest.raises(PaperStrategyEvaluationError, match="pending"):
        evaluate_fixture(
            state=state_with_pending,
            implementation=implementation,
            repository=repository,
            registry=registry,
            source=source,
        )
    assert implementation.contexts == []


def test_missing_exact_version_has_no_latest_fallback() -> None:
    implementation = FixtureStrategy()
    repository = RecordingRepository({})
    registry = RecordingRegistry(implementation)
    source = RecordingSource(bars_for)

    with pytest.raises(PaperStrategyEvaluationError, match="does not exist"):
        evaluate_current_paper_strategy(
            SESSION,
            strategy_version_id=VERSION_ID,
            parameter_values={"threshold": 1},
            state=None,
            financial_position_state=FinancialPositionState.FLAT,
            now=NOW,
            strategy_repository=repository,  # type: ignore[arg-type]
            strategy_registry=registry,  # type: ignore[arg-type]
            analytical_source=source,
            market_specification=MARKET,
        )
    assert source.calls == []


def test_registry_provenance_mismatch_fails_closed_without_source_read() -> None:
    registry = create_production_strategy_registry(ROOT)
    implementation = registry.get(
        "candle_confirmation_break",
        implementation_key="candle_confirmation_break.v1",
    ).implementation
    version_id = uuid4()
    row = persisted_row(
        version_id,
        implementation.definition,
        source_fingerprint="0" * 64,
    )
    repository = RecordingRepository({version_id: row})
    source = RecordingSource(bars_for)

    with pytest.raises(StrategyVersionUnavailableError, match="fingerprint"):
        evaluate_current_paper_strategy(
            SESSION,
            strategy_version_id=version_id,
            parameter_values={
                "confirmation_bars": 1,
                "stop_buffer_pips": "20",
                "target_r": "1.5",
            },
            state=None,
            financial_position_state=FinancialPositionState.FLAT,
            now=NOW,
            strategy_repository=repository,  # type: ignore[arg-type]
            strategy_registry=registry,
            analytical_source=source,
            market_specification=MARKET,
        )

    assert source.calls == []


def test_restored_state_must_contain_a_prior_frontier() -> None:
    implementation = FixtureStrategy()
    repository, registry, source = make_dependencies(implementation)
    state = StrategyStateEnvelope(
        1,
        None,
        StrategyStatePayloadDocument.from_mapping("paper_fixture.v1", 1, {}),
    )

    with pytest.raises(PaperStrategyEvaluationError, match="prior"):
        evaluate_fixture(
            state=state,
            implementation=implementation,
            repository=repository,
            registry=registry,
            source=source,
        )

    assert source.calls == []
    assert implementation.contexts == []


def test_current_production_candle_strategy_returns_existing_evaluation() -> None:
    registry = create_production_strategy_registry(ROOT)
    implementation = registry.get(
        "candle_confirmation_break",
        implementation_key="candle_confirmation_break.v1",
    ).implementation
    definition = implementation.definition
    version_id = uuid4()
    row = persisted_row(
        version_id,
        definition,
        source_fingerprint=registry.get(
            definition.strategy_key,
            implementation_key=definition.implementation_key,
        ).source_archive.fingerprint,
    )
    repository = RecordingRepository({version_id: row})
    source = RecordingSource(
        lambda start, end: tuple(
            bar(
                item,
                open_price="1.1000",
                high="1.1100" if item.minute == 0 else "1.1010",
                low="1.0980" if item.minute == 0 else "1.0990",
                close="1.1060" if item.minute == 0 else "1.1000",
            )
            for item, _ in eligible_m15_windows(start, end)
        )
    )

    result = evaluate_current_paper_strategy(
        SESSION,
        strategy_version_id=version_id,
        parameter_values={
            "confirmation_bars": 1,
            "stop_buffer_pips": "20",
            "target_r": "1.5",
        },
        state=None,
        financial_position_state=FinancialPositionState.FLAT,
        now=NOW,
        strategy_repository=repository,  # type: ignore[arg-type]
        strategy_registry=registry,
        analytical_source=source,
        market_specification=MARKET,
    )

    assert type(result) is StrategyEvaluation
    assert result.decision.action is Action.OPEN_LONG
    assert result.decision.entry_policy is EntryPolicy.IMMEDIATE
    assert result.next_state.last_evaluated_bar_end == datetime(
        2026, 1, 5, 10, 15, tzinfo=UTC
    )


def test_current_production_ema_strategy_preserves_price_trigger_handoff() -> None:
    registry = create_production_strategy_registry(ROOT)
    implementation = registry.get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    ).implementation
    definition = implementation.definition
    version_id = uuid4()
    entry = registry.get(
        definition.strategy_key,
        implementation_key=definition.implementation_key,
    )
    row = persisted_row(
        version_id,
        definition,
        source_fingerprint=entry.source_archive.fingerprint,
    )
    repository = RecordingRepository({version_id: row})

    def ema_bars(start: datetime, end: datetime) -> tuple[Bar, ...]:
        windows = eligible_m15_windows(start, end)
        values: list[Bar] = [bar(item) for item, _ in windows]
        values[-2] = bar(
            windows[-2][0],
            open_price="1.1020",
            high="1.1030",
            low="1.0995",
            close="1.1010",
        )
        values[-1] = bar(
            windows[-1][0],
            open_price="1.1000",
            high="1.1040",
            low="1.0980",
            close="1.1035",
        )
        return tuple(values)

    source = RecordingSource(ema_bars)
    request_start, request_end = required_warmup_range(
        datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
        datetime(2026, 1, 5, 10, 15, tzinfo=UTC),
        definition.required_historical_context_bars,
    )
    history_with_reference = ema_bars(request_start, request_end)[:-1]
    restored_evaluation = evaluate_strategy(
        implementation,
        StrategyContext(
            history_with_reference[-1].end_time,
            Instrument.EUR_USD,
            history_with_reference,
            market=MARKET,
            position=PositionState.FLAT,
            exposure_allowed=True,
        ),
        StrategyParameters(),
        initial_strategy_state(implementation),
    )
    assert isinstance(restored_evaluation.next_state, StrategyStateEnvelope)
    result = evaluate_current_paper_strategy(
        SESSION,
        strategy_version_id=version_id,
        parameter_values={
            "ema_period": 100,
            "atr_period": 14,
            "stop_buffer": "0.5",
            "target_r": "1.7",
            "expiry_window": 5,
        },
        state=restored_evaluation.next_state,
        financial_position_state=FinancialPositionState.FLAT,
        now=NOW,
        strategy_repository=repository,  # type: ignore[arg-type]
        strategy_registry=registry,
        analytical_source=source,
        market_specification=MARKET,
    )

    assert type(result) is StrategyEvaluation
    assert result.decision.entry_policy is EntryPolicy.PRICE_TRIGGERED
    assert isinstance(result.next_state, StrategyStateEnvelope)
    assert result.next_state.pending_entry is not None
    assert result.next_state.pending_entry.decision_frontier == datetime(
        2026, 1, 5, 10, 15, tzinfo=UTC
    )
