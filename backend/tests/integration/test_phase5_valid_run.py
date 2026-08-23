"""Evidence regressions for the Phase 5 configuration-to-Phase 4 runner path."""

import os
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from urllib.parse import urlparse

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.experiments.configuration import ExperimentConfigurationService
from backend.experiments.lifecycle import (
    ExperimentLifecycleDiagnostic,
    ExperimentRunService,
)
from backend.experiments.runner import (
    ExperimentRunner,
    Phase4RunnerComparisonDiagnostic,
)
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.experiment_repository import ExperimentRepository
from backend.persistence.models import (
    DatasetSnapshotBarModel,
    DatasetSnapshotModel,
    ExperimentAccountModel,
    ExperimentEquityPointModel,
    ExperimentModel,
    ExperimentResultModel,
    MarketBarModel,
    PositionModel,
    StrategyVersionModel,
    TradeModel,
    VenueInstrumentModel,
)
from backend.tests.integration.test_golden_flows import (
    PARAMETERS,
    START,
    _registry,
    _seed,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url() -> str:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.fail("ATLAS_TEST_DATABASE_URL is required for integration tests")
    if not urlparse(value).path.rsplit("/", 1)[-1].endswith("_test"):
        pytest.fail("integration tests require a database name ending in _test")
    return value


def _runner_inputs(session: Session, experiment_id):
    experiment = session.get(ExperimentModel, experiment_id)
    assert experiment is not None
    version = session.get(StrategyVersionModel, experiment.strategy_version_id)
    snapshot = session.get(DatasetSnapshotModel, experiment.dataset_snapshot_id)
    venue = session.get(VenueInstrumentModel, experiment.venue_instrument_id)
    account = session.get(ExperimentAccountModel, experiment_id)
    assert version is not None and snapshot is not None and venue is not None
    assert account is not None
    return {
        "strategy_version_id": experiment.strategy_version_id,
        "strategy_fingerprint": version.source_fingerprint,
        "dataset_snapshot_id": experiment.dataset_snapshot_id,
        "dataset_fingerprint": snapshot.fingerprint,
        "member_count": session.scalar(
            select(func.count()).select_from(DatasetSnapshotBarModel).where(
                DatasetSnapshotBarModel.dataset_snapshot_id == snapshot.id
            )
        ),
        "venue_instrument_id": experiment.venue_instrument_id,
        "venue": (venue.provider, venue.provider_symbol),
        "trading_start": experiment.trading_start,
        "trading_end": experiment.trading_end,
        "starting_capital": experiment.starting_capital,
        "risk_per_trade": experiment.risk_per_trade,
        "parameter_snapshot": experiment.parameter_snapshot,
        "risk_config": experiment.risk_config,
        "simulation_config": experiment.simulation_config,
        "model_version": experiment.model_version,
        "account": (
            account.base_currency,
            account.starting_capital,
            account.realized_pnl,
            account.unrealized_pnl,
            account.equity,
        ),
        "position": session.scalar(
            select(PositionModel.state).where(
                PositionModel.experiment_id == experiment_id
            )
        ),
        "status": experiment.status,
    }


@pytest.mark.parametrize("trading_end, expected_trades", [(1590, True), (1515, False)])
def test_phase5_candidate_matches_direct_phase4_baseline(
    database_url: str, trading_end: int, expected_trades: bool
) -> None:
    from sqlalchemy import create_engine

    engine = configure_utc_session_timezone(create_engine(database_url))
    try:
        with Session(engine) as session, session.begin():
            session.execute(
                text(
                    "TRUNCATE experiments, dataset_snapshots, market_bars, "
                    "strategy_versions, strategies, venue_instruments, "
                    "instruments CASCADE"
                )
            )
            baseline_id, snapshot_id, version_id = _seed(
                session, "LONG", phase4=True
            )
            if trading_end == 1515:
                source = session.get(ExperimentModel, baseline_id)
                assert source is not None
                source_snapshot = session.get(DatasetSnapshotModel, snapshot_id)
                assert source_snapshot is not None
                zero_snapshot = DatasetSnapshotModel(
                    venue_instrument_id=source_snapshot.venue_instrument_id,
                    base_resolution=source_snapshot.base_resolution,
                    components=source_snapshot.components,
                    coverage_start=source_snapshot.coverage_start,
                    coverage_end=START + timedelta(minutes=trading_end),
                    alignment_convention=source_snapshot.alignment_convention,
                    session_policy=source_snapshot.session_policy,
                    fingerprint_schema=source_snapshot.fingerprint_schema,
                    fingerprint=sha256(b"phase5-zero-regression").hexdigest(),
                    integrity_summary=source_snapshot.integrity_summary,
                )
                session.add(zero_snapshot)
                session.flush()
                bars = session.scalars(
                    select(MarketBarModel).where(
                        MarketBarModel.venue_instrument_id
                        == source_snapshot.venue_instrument_id,
                        MarketBarModel.start_time
                        < START + timedelta(minutes=trading_end),
                    )
                )
                session.add_all(
                    DatasetSnapshotBarModel(
                        dataset_snapshot_id=zero_snapshot.id, market_bar_id=bar.id
                    )
                    for bar in bars
                )
                snapshot_id = zero_snapshot.id
                baseline = ExperimentRepository().create(
                    session,
                    strategy_version_id=source.strategy_version_id,
                    dataset_snapshot_id=snapshot_id,
                    venue_instrument_id=source.venue_instrument_id,
                    trading_start=source.trading_start,
                    trading_end=START + timedelta(minutes=trading_end),
                    starting_capital=source.starting_capital,
                    risk_per_trade=source.risk_per_trade,
                    parameter_snapshot=source.parameter_snapshot,
                    risk_config=source.risk_config,
                    simulation_config=source.simulation_config,
                    model_version=source.model_version,
                )
                ExperimentRepository().create_account_and_position(session, baseline)
                baseline_id = baseline.id
            service = ExperimentConfigurationService(_registry())
            candidate = service.create(
                session,
                strategy_version_id=version_id,
                dataset_snapshot_id=snapshot_id,
                trading_start=START + timedelta(minutes=1500),
                trading_end=START + timedelta(minutes=trading_end),
                starting_capital=Decimal("10000"),
                risk_per_trade=Decimal("0.01"),
                parameters=PARAMETERS,
                slippage_ticks=0,
                commission_per_unit=Decimal("0.10"),
            )
            candidate_id = candidate.id
            baseline_inputs = _runner_inputs(session, baseline_id)
            candidate_inputs = _runner_inputs(session, candidate_id)
            assert baseline_inputs | {"status": "PENDING"} == candidate_inputs

        with Session(engine) as session, session.begin():
            baseline_diagnostics = []
            baseline_comparisons: list[Phase4RunnerComparisonDiagnostic] = []
            baseline_result = ExperimentRunner(
                strategy_registry=_registry(),
                value_error_diagnostic_sink=baseline_diagnostics.append,
                comparison_diagnostic_sink=baseline_comparisons.append,
            ).run(session, baseline_id)
            assert baseline_result.status == "COMPLETED", (
                baseline_result.failure,
                [
                    (record.stage.value, record.reason_code)
                    for record in baseline_diagnostics
                ],
            )
            baseline_inputs_at_entry = _runner_inputs(session, baseline_id)

        candidate_diagnostics = []
        candidate_comparisons: list[Phase4RunnerComparisonDiagnostic] = []
        lifecycle_diagnostics: list[ExperimentLifecycleDiagnostic] = []
        candidate_result = ExperimentRunService(
            lambda: Session(engine),
            ExperimentRunner(
                strategy_registry=_registry(),
                value_error_diagnostic_sink=candidate_diagnostics.append,
                comparison_diagnostic_sink=candidate_comparisons.append,
            ),
            lifecycle_diagnostic_sink=lifecycle_diagnostics.append,
        ).run(candidate_id)
        assert candidate_result.status == "COMPLETED", (
            candidate_result.failure,
            [record.as_dict() for record in candidate_diagnostics],
        )
        assert [record.stage.value for record in lifecycle_diagnostics] == [
            "RUNNER_RETURN",
            "FLUSH",
            "COMMIT",
            "FINAL_READ",
        ]
        assert all(record.exception_class is None for record in lifecycle_diagnostics)
        assert [record.checkpoint for record in baseline_comparisons] == [
            "PRE_EXECUTION", "TERMINAL_RETURN"
        ]
        assert [record.checkpoint for record in candidate_comparisons] == [
            "PRE_EXECUTION", "TERMINAL_RETURN"
        ]
        baseline_pre, baseline_terminal = baseline_comparisons
        candidate_pre, candidate_terminal = candidate_comparisons
        assert (
            baseline_pre.as_dict() | {"checkpoint": "PRE_EXECUTION"}
            == candidate_pre.as_dict()
        )
        assert (
            baseline_terminal.terminal_status
            == candidate_terminal.terminal_status
            == "COMPLETED"
        )
        assert (
            baseline_terminal.failure_category is None
            and candidate_terminal.failure_category is None
        )

        with Session(engine) as session:
            assert _runner_inputs(session, candidate_id)["status"] == "COMPLETED"
            assert session.get(ExperimentResultModel, baseline_id) is not None
            assert session.get(ExperimentResultModel, candidate_id) is not None
            assert (
                session.scalar(
                    select(TradeModel.id).where(TradeModel.experiment_id == baseline_id)
                )
                is not None
            ) is expected_trades
            assert (
                session.scalar(
                    select(TradeModel.id).where(
                        TradeModel.experiment_id == candidate_id
                    )
                )
                is not None
            ) is expected_trades
            assert session.scalar(
                    select(ExperimentEquityPointModel.sequence_number).where(
                    ExperimentEquityPointModel.experiment_id == candidate_id
                )
            ) is not None
            assert (
                baseline_inputs_at_entry["model_version"]
                == "PHASE4_HISTORICAL_EXECUTION_V1"
            )
    finally:
        engine.dispose()
