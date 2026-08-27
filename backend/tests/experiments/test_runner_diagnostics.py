from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from backend.experiments.configuration import missing_analytical_frontiers
from backend.experiments.runner import (
    ExperimentRunner,
    Phase4DiagnosticStage,
    Phase4RunnerComparisonDiagnostic,
    Phase4ValueErrorDiagnostic,
    _diagnostic_reason,
    classify_runner_value_error,
    result_quality_for_gaps,
    terminal_protection_observation,
)
from backend.market_data.session_calendar import eligible_m15_windows


def test_known_value_error_diagnostic_has_only_closed_fields() -> None:
    record = Phase4ValueErrorDiagnostic(
        "experiment_runner_value_error",
        uuid4(),
        "PHASE4_HISTORICAL_EXECUTION_V1",
        "PHASE4",
        Phase4DiagnosticStage.M15_AGGREGATION,
        _diagnostic_reason("no final eligible M1 quote"),
    )

    assert record.as_dict() == {
        "event": "experiment_runner_value_error",
        "experiment_id": str(record.experiment_id),
        "model_version": "PHASE4_HISTORICAL_EXECUTION_V1",
        "run_path": "PHASE4",
        "stage": "m15_aggregation",
        "reason_code": "FINAL_QUOTE_MISSING",
    }


    records = []
    runner = ExperimentRunner(
        strategy_registry=SimpleNamespace(), value_error_diagnostic_sink=records.append
    )
    experiment = SimpleNamespace(
        id=uuid4(), model_version="PHASE4_HISTORICAL_EXECUTION_V1"
    )
    runner._emit_value_error_diagnostic(
        experiment,
        Phase4DiagnosticStage.CLOCK_MATERIALIZATION,
        ValueError("incomplete M1 observation at 2026-01-06T01:00:00-05:00"),
    )
    assert records[0].as_dict()["reason_code"] == "INCOMPLETE_M1_OBSERVATION"
    assert records[0].as_dict()["at"] == "2026-01-06T06:00:00Z"


def test_result_quality_prioritizes_data_uncertainty_then_ambiguity() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=1)
    gap = SimpleNamespace(blocked=True, start_time=start, end_time=end)
    assert result_quality_for_gaps((), (), start, end) == "DETERMINED"
    assert result_quality_for_gaps((), (), start, end, ambiguous=True) == (
        "CONSERVATIVE_AMBIGUITY_RESOLVED"
    )
    assert result_quality_for_gaps((gap,), (), start, end, ambiguous=True) == "DEGRADED"


def test_accounting_invariant_has_explicit_failure_code() -> None:
    category, code = classify_runner_value_error(ValueError("Trade and Position directions disagree"))
    assert category.value == "VALIDATION"
    assert code == "ACCOUNTING_INVARIANT"


def test_unknown_hostile_value_error_is_unclassified_and_not_emitted() -> None:
    hostile = "password=secret; SELECT * FROM users; /private/source.py"
    assert _diagnostic_reason(hostile) == "UNCLASSIFIED_VALUE_ERROR"

    records = []
    runner = ExperimentRunner(
        strategy_registry=SimpleNamespace(),
        value_error_diagnostic_sink=records.append,
    )
    experiment = SimpleNamespace(
        id=uuid4(), model_version="PHASE4_HISTORICAL_EXECUTION_V1"
    )
    runner._emit_value_error_diagnostic(
        experiment, Phase4DiagnosticStage.PRECONDITIONS, ValueError(hostile)
    )

    assert records[0].reason_code == "UNCLASSIFIED_VALUE_ERROR"
    assert hostile not in str(records[0].as_dict())


def test_absent_or_raising_sink_cannot_escape() -> None:
    experiment = SimpleNamespace(
        id=uuid4(), model_version="PHASE4_HISTORICAL_EXECUTION_V1"
    )
    runner = ExperimentRunner(strategy_registry=SimpleNamespace())
    runner._emit_value_error_diagnostic(
        experiment, Phase4DiagnosticStage.RESULT_FINALIZATION, ValueError("unknown")
    )

    def raising_sink(_record: Phase4ValueErrorDiagnostic) -> None:
        raise RuntimeError("sink failure")

    runner = ExperimentRunner(
        strategy_registry=SimpleNamespace(), value_error_diagnostic_sink=raising_sink
    )
    runner._emit_value_error_diagnostic(
        experiment, Phase4DiagnosticStage.RESULT_FINALIZATION, ValueError("unknown")
    )


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


def test_internal_native_analytical_frontier_is_explicitly_missing() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert missing_analytical_frontiers(
        {start, start + timedelta(minutes=30)}, start, start + timedelta(minutes=45)
    ) == (start + timedelta(minutes=15),)


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

def test_comparison_record_has_exact_closed_shape_and_no_raw_values() -> None:
    record = Phase4RunnerComparisonDiagnostic(
        "experiment_runner_comparison", "PRE_EXECUTION",
        Phase4DiagnosticStage.PRE_EXECUTION_INPUTS,
        "RESOLVED_SAME_ROW", "sha256:" + "a" * 64,
        "RESOLVED_SAME_ROW", "sha256:" + "b" * 64, 3,
        "sha256:" + "c" * 64, "sha256:" + "d" * 64,
        "sha256:" + "e" * 64, "sha256:" + "f" * 64,
        "sha256:" + "0" * 64, "sha256:" + "1" * 64,
        "sha256:" + "2" * 64, "sha256:" + "3" * 64,
        "sha256:" + "4" * 64, None, None, None, None,
    )
    serialized = record.as_dict()
    assert set(serialized) == {
        "event", "checkpoint", "stage", "strategy_identity",
        "strategy_contract_digest", "snapshot_identity", "snapshot_contract_digest",
        "snapshot_member_count", "snapshot_membership_digest", "parameters_digest",
        "risk_digest", "simulation_digest", "period_digest", "capital_digest",
        "financial_projection_digest", "effective_execution_digest",
        "seed_profile_digest",
        "runner_inputs_digest", "terminal_status", "failure_category", "failure_code",
    }
    assert "password" not in str(serialized)
    assert "SELECT" not in str(serialized)
