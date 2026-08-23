from backend.experiments.lifecycle import (
    ExperimentLifecycleDiagnostic,
    LifecycleDiagnosticStage,
    _exception_class,
    _sqlstate,
)


def test_lifecycle_record_is_exactly_six_closed_fields() -> None:
    record = ExperimentLifecycleDiagnostic(
        LifecycleDiagnosticStage.RUNNER_RETURN,
        None,
        None,
        "UTC",
        123,
        "0007_phase_5_metric_contract",
    )
    assert record.as_dict() == {
        "stage": "RUNNER_RETURN",
        "exception_class": None,
        "sqlstate": None,
        "show_time_zone": "UTC",
        "backend_pid": 123,
        "alembic_revision": "0007_phase_5_metric_contract",
    }
    assert set(record.as_dict()) == {
        "stage",
        "exception_class",
        "sqlstate",
        "show_time_zone",
        "backend_pid",
        "alembic_revision",
    }


def test_exception_and_sqlstate_mapping_is_closed_without_formatting() -> None:
    class Hostile(Exception):
        sqlstate = "DROP"

        def __str__(self) -> str:
            raise AssertionError("message must not be formatted")

    class Structured(Exception):
        sqlstate = "23505"

    assert _exception_class(Hostile("secret")) == "UNCLASSIFIED_EXCEPTION"
    assert _sqlstate(Hostile("secret")) is None
    assert _sqlstate(Structured("secret")) == "23505"
