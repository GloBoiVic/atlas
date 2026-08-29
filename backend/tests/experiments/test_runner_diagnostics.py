import ast
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn, Protocol, cast
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session as OrmSession

import backend.experiments.runner as runner_module
from backend.experiments.configuration import missing_analytical_frontiers
from backend.experiments.runner import (
    ExperimentDiagnosticStage,
    ExperimentRunner,
    FailureCategory,
    _failure_category_for_stage,
    classify_runner_value_error,
    result_quality_for_gaps,
    terminal_protection_observation,
)
from backend.market_data.session_calendar import eligible_m15_windows
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.models import DatasetSnapshotModel
from backend.strategies.registry import StrategyVersionUnavailableError


class _DataclassParamsView(Protocol):
    frozen: bool


class _DataclassTypeView(Protocol):
    __dataclass_params__: _DataclassParamsView


def test_result_quality_prioritizes_data_uncertainty_then_ambiguity() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=1)
    gap = SimpleNamespace(blocked=True, start_time=start, end_time=end)
    assert result_quality_for_gaps((), (), start, end) == "DETERMINED"
    assert result_quality_for_gaps((), (), start, end, ambiguous=True) == (
        "CONSERVATIVE_AMBIGUITY_RESOLVED"
    )
    assert result_quality_for_gaps((gap,), (), start, end, ambiguous=True) == "DEGRADED"


def test_failure_classification_comes_from_typed_ownership_not_message_text() -> None:
    category, code = classify_runner_value_error(
        ValueError("Trade and Position directions disagree"),
        category=FailureCategory.VALIDATION,
        code="ACCOUNTING_INVARIANT",
    )
    assert category.value == "VALIDATION"
    assert code == "ACCOUNTING_INVARIANT"
    assert classify_runner_value_error(
        ValueError("completely different wording"),
        category=FailureCategory.VALIDATION,
        code="ACCOUNTING_INVARIANT",
    ) == (category, code)


def test_runner_seams_have_narrow_failure_owners() -> None:
    assert (
        _failure_category_for_stage(ExperimentDiagnosticStage.SNAPSHOT_MEMBER_LOAD)
        == FailureCategory.MARKET_DATA
    )
    assert (
        _failure_category_for_stage(ExperimentDiagnosticStage.DECISION_EVALUATION)
        == FailureCategory.STRATEGY
    )
    assert classify_runner_value_error(
        ValueError("risk rejected"), category=FailureCategory.RISK, code="RISK_REJECTED"
    ) == (FailureCategory.RISK, "RISK_REJECTED")
    assert classify_runner_value_error(
        ValueError("execution failed"),
        category=FailureCategory.EXECUTION,
        code="EXECUTION_REJECTED",
    ) == (FailureCategory.EXECUTION, "EXECUTION_REJECTED")
    assert classify_runner_value_error(
        ValueError("sqlalchemy wording"),
        category=FailureCategory.PERSISTENCE,
        code="PERSISTENCE_FAILURE",
    ) == (FailureCategory.PERSISTENCE, "PERSISTENCE_FAILURE")
    # The broad engine fallback is deliberately validation-owned, not persistence.
    assert FailureCategory.VALIDATION != FailureCategory.PERSISTENCE


def test_v2_unexpected_engine_failure_is_not_persistence() -> None:
    failures = []

    class ExplodingStrategies:
        def get_version(self, _session, _strategy_version_id):
            raise RuntimeError("engine exploded outside the database")

    class FailureRepository:
        def mark_failed(self, _session, experiment_id, **kwargs):
            failures.append((experiment_id, kwargs))

    experiment = SimpleNamespace(
        id=uuid4(), status="RUNNING", strategy_version_id=uuid4()
    )
    runner = ExperimentRunner(
        strategy_registry=SimpleNamespace(),
        strategy_repository=ExplodingStrategies(),
        experiment_repository=FailureRepository(),
    )

    result = runner._run_v2(SimpleNamespace(), experiment)

    assert result.status == "FAILED"
    assert result.failure is not None
    assert result.failure.category is FailureCategory.VALIDATION
    assert result.failure.code == "UNEXPECTED_ENGINE_FAILURE"
    assert failures[0][1]["category"] == "VALIDATION"
    assert failures[0][1]["code"] == "UNEXPECTED_ENGINE_FAILURE"


@pytest.mark.parametrize("error", [KeyError("unrelated"), IndexError("unrelated")])
def test_v2_unrelated_lookup_errors_are_not_strategy_version_unavailable(error) -> None:
    class Strategies:
        def get_version(self, _session, _strategy_version_id):
            return object()

    class Registry:
        def implementation_for_version(self, _version):
            raise error

    class FailureRepository:
        def mark_failed(self, _session, _experiment_id, **_kwargs):
            return None

    experiment = SimpleNamespace(
        id=uuid4(), status="RUNNING", strategy_version_id=uuid4()
    )
    runner = ExperimentRunner(
        strategy_registry=Registry(),
        strategy_repository=Strategies(),
        experiment_repository=FailureRepository(),
    )

    # The database/domain conversion is not part of this seam regression.
    import backend.experiments.runner as runner_module

    original = runner_module.version_to_domain
    runner_module.version_to_domain = lambda row: row
    try:
        result = runner._run_v2(SimpleNamespace(), experiment)
    finally:
        runner_module.version_to_domain = original

    assert result.failure is not None
    assert result.failure.code == "UNEXPECTED_ENGINE_FAILURE"
    assert result.failure.code != "STRATEGY_VERSION_UNAVAILABLE"


def test_v2_registry_unavailability_is_strategy_version_unavailable() -> None:
    class Strategies:
        def get_version(self, _session, _strategy_version_id):
            return object()

    class Registry:
        def implementation_for_version(self, _version):
            raise StrategyVersionUnavailableError("not registered")

    class FailureRepository:
        def mark_failed(self, _session, _experiment_id, **_kwargs):
            return None

    experiment = SimpleNamespace(
        id=uuid4(), status="RUNNING", strategy_version_id=uuid4()
    )
    runner = ExperimentRunner(
        strategy_registry=Registry(),
        strategy_repository=Strategies(),
        experiment_repository=FailureRepository(),
    )

    import backend.experiments.runner as runner_module

    original = runner_module.version_to_domain
    runner_module.version_to_domain = lambda row: row
    try:
        result = runner._run_v2(SimpleNamespace(), experiment)
    finally:
        runner_module.version_to_domain = original

    assert result.failure is not None
    assert result.failure.category is FailureCategory.STRATEGY
    assert result.failure.code == "STRATEGY_VERSION_UNAVAILABLE"


def test_terminal_sparse_absence_fails_closed_even_with_entry_observation() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    entry = SimpleNamespace(start_time=start, end_time=start + timedelta(minutes=1))
    assert terminal_protection_observation(
        (entry,), start, start + timedelta(minutes=15)
    ) is None


def test_terminal_quote_before_end_is_not_a_terminal_observation() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    quote = SimpleNamespace(start_time=start, end_time=start + timedelta(minutes=1))
    assert terminal_protection_observation(
        (quote,), start, start + timedelta(minutes=2)
    ) is None


def test_quality_distinguishes_material_and_non_material_gaps() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(minutes=15)
    non_material = SimpleNamespace(blocked=False, start_time=start, end_time=end)
    material = SimpleNamespace(blocked=True, start_time=start, end_time=end)
    assert result_quality_for_gaps((non_material,), (), start, end) == "DETERMINED"
    assert result_quality_for_gaps((material,), (), start, end) == "DEGRADED"


def test_closed_native_analytical_frontier_is_not_missing() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert missing_analytical_frontiers(
        {start, start + timedelta(minutes=30)}, start, start + timedelta(minutes=45)
    ) == ()


def test_weekend_session_closure_is_not_an_analytical_frontier_gap() -> None:
    start = datetime(2025, 1, 10, 21, 0, tzinfo=UTC)
    end = datetime(2025, 1, 13, 23, 0, tzinfo=UTC)
    eligible = eligible_m15_windows(start, end)

    assert eligible
    assert (
        missing_analytical_frontiers({item[0] for item in eligible}, start, end) == ()
    )


def test_internal_open_session_frontier_remains_a_gap() -> None:
    start = datetime(2025, 1, 6, 14, 0, tzinfo=UTC)
    end = datetime(2025, 1, 6, 16, 0, tzinfo=UTC)
    eligible = eligible_m15_windows(start, end)
    missing = eligible[len(eligible) // 2][0]

    analytical_starts = {item[0] for item in eligible} - {missing}
    assert missing_analytical_frontiers(analytical_starts, start, end) == (missing,)

def test_runner_has_one_authoritative_loop_and_no_superseded_seams() -> None:
    source = Path(__file__).parents[2].joinpath("experiments", "runner.py").read_text()
    module = ast.parse(source)
    runner = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "ExperimentRunner"
    )
    methods = {
        node.name: node for node in runner.body if isinstance(node, ast.FunctionDef)
    }
    run_calls = [
        node.func.attr
        for node in ast.walk(methods["run"])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    ]
    assert run_calls.count("_run_v2") == 1
    assert "_run_phase4" not in source
    assert "_open_and_close" not in source
    assert "aggregate_m1_to_m15" not in source
    assert "RunnerComparisonDiagnostic" not in source
    assert "Phase4ValueErrorDiagnostic" not in source
    assert "def _run_v2" in source
    assert "_complete_result" in source
    assert "_complete_phase4" not in source

    run_v2 = methods["_run_v2"]
    clock_calls = [
        node
        for node in ast.walk(run_v2)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "SimulationClock"
    ]
    assert clock_calls
    clock_call = clock_calls[0]
    sparse = next(
        keyword
        for keyword in clock_call.keywords
        if keyword.arg == "sparse_execution"
    )
    assert isinstance(sparse.value, ast.Constant) and sparse.value.value is True

    attributes = {
        node.attr for node in ast.walk(run_v2) if isinstance(node, ast.Attribute)
    }
    assert "aggregate_m1_to_m15" not in attributes
    assert "expiry_time" not in attributes
    assert any(
        isinstance(node, ast.Compare)
        and isinstance(node.ops[0], ast.Gt)
        and isinstance(node.left, ast.Attribute)
        and node.left.attr == "start_time"
        and any(
            isinstance(comparator, ast.Attribute)
            and comparator.attr == "decision_time"
            for comparator in node.comparators
        )
        for node in ast.walk(run_v2)
    )
    assert any(
        isinstance(node, ast.Attribute) and node.attr == "IMMEDIATE"
        for node in ast.walk(run_v2)
    )
    assert any(
        isinstance(node, ast.Compare)
        and isinstance(node.ops[0], ast.Lt)
        and isinstance(node.left, ast.Attribute)
        and node.left.attr == "consumed_count"
        and any(
            isinstance(comparator, ast.Attribute)
            and comparator.attr == "eligibility_limit"
            for comparator in node.comparators
        )
        for node in ast.walk(run_v2)
    )
    trigger_operators = {
        type(node.ops[0])
        for node in ast.walk(run_v2)
        if isinstance(node, ast.Compare)
        and any(
            isinstance(comparator, ast.Attribute)
            and comparator.attr == "trigger_price"
            for comparator in node.comparators
        )
    }
    assert {ast.Gt, ast.GtE, ast.Lt, ast.LtE} <= trigger_operators
    assert any(
        isinstance(node, ast.Attribute) and node.attr == "M15"
        for node in ast.walk(run_v2)
    )
    assert any(
        isinstance(node, ast.Attribute) and node.attr == "MID"
        for node in ast.walk(run_v2)
    )
    root = Path(__file__).parents[2]
    lifecycle = ast.parse(
        root.joinpath("experiments", "lifecycle.py").read_text()
    )
    lifecycle_run = next(
        node
        for node in ast.walk(lifecycle)
        if isinstance(node, ast.FunctionDef)
        and node.name == "run"
        and any(
            isinstance(parent, ast.ClassDef)
            and parent.name == "ExperimentRunService"
            for parent in lifecycle.body
        )
    )
    lifecycle_runner_calls = [
        node
        for node in ast.walk(lifecycle_run)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
    ]
    assert len(lifecycle_runner_calls) == 1
    runner_call = lifecycle_runner_calls[0]
    assert isinstance(runner_call.func, ast.Attribute)
    runner_owner = runner_call.func.value
    assert isinstance(runner_owner, ast.Attribute)
    assert runner_owner.attr == "_runner"
    app_source = root.joinpath("api", "app.py").read_text()
    assert app_source.count("ExperimentRunner(") == 1
    assert ".run(" not in app_source


def test_v2_malformed_risk_config_fails_before_empty_frame_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failures = []
    account = SimpleNamespace()
    position = SimpleNamespace(state="FLAT")
    snapshot = SimpleNamespace(id=uuid4(), venue_instrument_id=uuid4())
    venue = SimpleNamespace(instrument_id=uuid4(), provider="OANDA")
    instrument = SimpleNamespace(code="EUR_USD")

    class EmptyRows:
        def all(self) -> list[object]:
            return []

    class EmptyFrameSession:
        def __init__(self) -> None:
            self.scalar_calls = 0

        def get(self, model: type[object], _identifier: object) -> object:
            if model is DatasetSnapshotModel:
                return snapshot
            if model is runner_module.VenueInstrumentModel:
                return venue
            if model is runner_module.InstrumentModel:
                return instrument
            raise AssertionError(f"unexpected get model: {model}")

        def scalars(self, _statement: object) -> EmptyRows:
            return EmptyRows()

        def scalar(self, _statement: object) -> object:
            self.scalar_calls += 1
            return (account, position, None)[self.scalar_calls - 1]

    class Strategies:
        def get_version(self, _session: object, _strategy_version_id: object) -> object:
            return object()

    class Experiments:
        def mark_failed(
            self, _session: object, _experiment_id: object, **kwargs: object
        ) -> None:
            failures.append(kwargs)

    class EmptyClock:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def frames(self) -> tuple[object, ...]:
            return ()

        def observations(self) -> tuple[object, ...]:
            return ()

    def implementation_for_version(_version: Any) -> object:
        return object()

    def version_to_test_domain(_row: Any) -> Any:
        return SimpleNamespace(
            id=uuid4(), required_historical_context_bars=0, state_schema_version=2
        )

    def sample_equity(*_args: Any, **_kwargs: Any) -> None:
        return None

    def reject_completion(*_args: Any, **_kwargs: Any) -> NoReturn:
        pytest.fail("completed")

    experiment = SimpleNamespace(
        id=uuid4(),
        status="RUNNING",
        strategy_version_id=uuid4(),
        dataset_snapshot_id=uuid4(),
        trading_start=datetime(2026, 1, 1, tzinfo=UTC),
        trading_end=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        risk_per_trade=object(),
        parameter_snapshot={},
        simulation_config={},
    )
    runner = ExperimentRunner(
        strategy_registry=cast(
            Any, SimpleNamespace(implementation_for_version=implementation_for_version)
        ),
        strategy_repository=cast(Any, Strategies()),
        experiment_repository=cast(Any, Experiments()),
    )
    monkeypatch.setattr(
        runner_module,
        "version_to_domain",
        version_to_test_domain,
    )
    monkeypatch.setattr(runner_module, "SimulationClock", EmptyClock)
    monkeypatch.setattr(runner, "_sample_equity", sample_equity)
    monkeypatch.setattr(runner, "_complete_v2", reject_completion)

    result = cast(Any, runner)._run_v2(
        cast(OrmSession, EmptyFrameSession()), cast(Any, experiment)
    )

    assert result.status == "FAILED"
    assert result.failure is not None
    assert result.failure.code == "INVALID_INPUT"
    assert failures and failures[0]["code"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "schema", ["ATLAS_HISTORICAL_SNAPSHOT_V1", "UNKNOWN", None]
)
def test_unsupported_snapshot_schema_fails_without_legacy_runner(
    schema: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    experiment = SimpleNamespace(
        id=uuid4(),
        status="RUNNING",
        dataset_snapshot_id=uuid4(),
    )
    snapshot = SimpleNamespace(snapshot_schema=schema)
    failures = []

    class Experiments:
        def get(self, _session: object, _experiment_id: object) -> SimpleNamespace:
            return experiment

        def mark_failed(
            self, _session: object, _experiment_id: object, **kwargs: object
        ) -> None:
            failures.append(kwargs)

    class Session:
        def get(self, model: type[object], _snapshot_id: object) -> SimpleNamespace:
            assert model is DatasetSnapshotModel
            return snapshot

    runner = ExperimentRunner(
        strategy_registry=SimpleNamespace(),
        experiment_repository=cast(ExperimentRepository, Experiments()),
    )

    def reject_v2(*_args: object, **_kwargs: object) -> NoReturn:
        pytest.fail("legacy schema entered V2 loop")

    monkeypatch.setattr(runner, "_run_v2", reject_v2)

    result = runner.run(cast(OrmSession, Session()), experiment.id)

    assert result.status == "FAILED"
    assert result.failure is not None
    assert result.failure.code == "UNSUPPORTED_EXPERIMENT_MODEL"
    assert failures[0]["code"] == "UNSUPPORTED_EXPERIMENT_MODEL"


def test_pending_price_trigger_is_an_immutable_runner_handoff() -> None:
    pending_type = cast(type[Any], vars(runner_module)["_PendingPriceTrigger"])
    assert is_dataclass(pending_type)
    assert tuple(field.name for field in fields(pending_type)) == (
        "intent",
        "decision_frame",
        "decision",
    )
    params = cast(_DataclassTypeView, pending_type).__dataclass_params__
    assert params.frozen is True
    assert hasattr(pending_type, "__slots__")
