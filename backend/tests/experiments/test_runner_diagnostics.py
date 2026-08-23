from types import SimpleNamespace
from uuid import uuid4

from backend.experiments.runner import (
    ExperimentRunner,
    Phase4DiagnosticStage,
    Phase4RunnerComparisonDiagnostic,
    Phase4ValueErrorDiagnostic,
    _diagnostic_reason,
)


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
