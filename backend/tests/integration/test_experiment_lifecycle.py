from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Event, Thread

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.experiments.configuration import ExperimentConfigurationService
from backend.experiments.lifecycle import (
    ExperimentRunInfrastructureError,
    ExperimentRunService,
)
from backend.experiments.runner import (
    ExperimentFailure,
    ExperimentRunResult,
    FailureCategory,
)
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.models import ExperimentEquityPointModel, ExperimentModel
from backend.tests.integration.test_experiment_configuration import (
    _seed_configuration,
)
from backend.tests.integration.test_golden_flows import (
    PARAMETERS,
    START,
    _registry,
    database_url,  # noqa: F401
)

pytestmark = pytest.mark.integration


class GatedRunner:
    def __init__(self, *, failure: bool = False, error: bool = False) -> None:
        self.entered = Event()
        self.release = Event()
        self.calls = 0
        self.failure = failure
        self.error = error

    def run(self, session: Session, experiment_id):
        self.calls += 1
        self.entered.set()
        if self.error:
            raise RuntimeError("deliberately gated infrastructure failure")
        if not self.release.wait(timeout=10):
            raise RuntimeError("test gate timed out")
        if self.failure:
            repo = ExperimentRepository()
            repo.mark_failed(
                session,
                experiment_id,
                category=FailureCategory.STRATEGY.value,
                code="STRATEGY_EVALUATION_FAILED",
                detail="Strategy evaluation failed",
                completed_at=datetime.now(UTC),
            )
            return ExperimentRunResult(
                experiment_id,
                "FAILED",
                False,
                ExperimentFailure(
                    FailureCategory.STRATEGY,
                    "STRATEGY_EVALUATION_FAILED",
                    "Strategy evaluation failed",
                ),
            )
        ExperimentRepository().mark_completed(session, experiment_id, datetime.now(UTC))
        return ExperimentRunResult(experiment_id, "COMPLETED", False)


def _create(engine, count: int = 1):
    with Session(engine) as session:
        version, snapshot = _seed_configuration(session)
        service = ExperimentConfigurationService(_registry())
        experiments = [
            service.create(
                session,
                strategy_version_id=version.id,
                dataset_snapshot_id=snapshot.id,
                trading_start=START + timedelta(minutes=1500),
                trading_end=START + timedelta(minutes=1590),
                starting_capital=Decimal("10000"),
                risk_per_trade=Decimal("0.01"),
                parameters=PARAMETERS,
                slippage_ticks=0,
                commission_per_unit=Decimal("0"),
            )
            for _ in range(count)
        ]
        session.commit()
        return (
            experiments[0].id
            if count == 1
            else tuple(item.id for item in experiments)
        )


def test_running_claim_is_visible_while_run_is_gated(database_url: str) -> None:  # noqa: F811
    from sqlalchemy import create_engine

    from backend.persistence.database import configure_utc_session_timezone

    engine = configure_utc_session_timezone(create_engine(database_url))
    experiment_id = _create(engine)
    runner = GatedRunner()
    service = ExperimentRunService(lambda: Session(engine), runner)  # type: ignore[arg-type]
    thread = Thread(target=lambda: service.run(experiment_id))
    thread.start()
    assert runner.entered.wait(timeout=10)
    with Session(engine) as status_session:
        assert status_session.scalar(
            select(ExperimentModel.status).where(ExperimentModel.id == experiment_id)
        ) == "RUNNING"
    runner.release.set()
    thread.join(timeout=10)
    assert not thread.is_alive()
    engine.dispose()


def test_domain_failure_and_terminal_retry_are_safe(database_url: str) -> None:  # noqa: F811
    from sqlalchemy import create_engine

    from backend.persistence.database import configure_utc_session_timezone

    engine = configure_utc_session_timezone(create_engine(database_url))
    experiment_id = _create(engine)
    runner = GatedRunner(failure=True)
    runner.release.set()
    service = ExperimentRunService(lambda: Session(engine), runner)  # type: ignore[arg-type]
    assert service.run(experiment_id).status == "FAILED"
    assert service.run(experiment_id).status == "FAILED"
    assert runner.calls == 1
    engine.dispose()


def test_duplicate_commands_serialize_on_the_experiment_row(database_url: str) -> None:  # noqa: F811
    from sqlalchemy import create_engine

    from backend.persistence.database import configure_utc_session_timezone

    engine = configure_utc_session_timezone(create_engine(database_url))
    experiment_id = _create(engine)
    runner = GatedRunner()
    service = ExperimentRunService(lambda: Session(engine), runner)  # type: ignore[arg-type]
    results = []
    first = Thread(target=lambda: results.append(service.run(experiment_id)))
    second = Thread(target=lambda: results.append(service.run(experiment_id)))
    first.start()
    assert runner.entered.wait(timeout=10)
    second.start()
    runner.release.set()
    first.join(timeout=10)
    second.join(timeout=10)
    assert not first.is_alive() and not second.is_alive()
    assert [result.status for result in results] == ["COMPLETED", "COMPLETED"]
    assert runner.calls == 1
    engine.dispose()


def test_clean_recovery_and_committed_partial_state_fail_closed(
    database_url: str,  # noqa: F811
) -> None:  # noqa: F811
    from sqlalchemy import create_engine

    from backend.persistence.database import configure_utc_session_timezone

    engine = configure_utc_session_timezone(create_engine(database_url))
    clean_id, partial_id = _create(engine, count=2)
    with Session(engine) as session, session.begin():
        session.execute(
            update(ExperimentModel)
            .where(ExperimentModel.id.in_([clean_id, partial_id]))
            .values(status="RUNNING")
        )
        session.add(
            ExperimentEquityPointModel(
                experiment_id=partial_id,
                sequence_number=1,
                observed_at=START,
                balance=10000,
                realized_pnl=0,
                unrealized_pnl=0,
                equity=10000,
                running_peak=10000,
                drawdown_amount=0,
                drawdown_percent=0,
            )
        )
    runner = GatedRunner()
    runner.release.set()
    service = ExperimentRunService(lambda: Session(engine), runner)  # type: ignore[arg-type]
    assert service.run(clean_id).status == "COMPLETED"
    partial_result = service.run(partial_id)
    assert partial_result.status == "FAILED"
    with Session(engine) as session:
        row = session.get(ExperimentModel, partial_id)
        assert row is not None
        assert row.failure_code == "INCOMPLETE_RUN_STATE"
    engine.dispose()


def test_infrastructure_failure_has_durable_sanitized_fallback(
    database_url: str,  # noqa: F811
) -> None:  # noqa: F811
    from sqlalchemy import create_engine

    from backend.persistence.database import configure_utc_session_timezone

    engine = configure_utc_session_timezone(create_engine(database_url))
    experiment_id = _create(engine)
    runner = GatedRunner(error=True)
    service = ExperimentRunService(lambda: Session(engine), runner)  # type: ignore[arg-type]
    with pytest.raises(ExperimentRunInfrastructureError, match="retry the Experiment"):
        service.run(experiment_id)
    with Session(engine) as session:
        row = session.get(ExperimentModel, experiment_id)
        assert row is not None
        assert row.status == "FAILED"
        assert row.failure_code == "PERSISTENCE_FAILURE"
        assert "deliberately" not in (row.failure_detail or "")
    engine.dispose()
