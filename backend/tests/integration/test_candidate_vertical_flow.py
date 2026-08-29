# ruff: noqa: E501
"""PostgreSQL proof of the registered Candle Confirmation Break V2 path."""

from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA_V2,
    GAP_POLICY_V1,
    SESSION_POLICY,
    DatasetSnapshot,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.domain.strategy import StrategyVersion
from backend.experiments.configuration import ExperimentConfigurationService
from backend.experiments.lifecycle import ExperimentRunService
from backend.experiments.results import ExperimentResultReadService
from backend.experiments.runner import ExperimentRunner
from backend.market_data.fingerprint import (
    bar_content_fingerprint,
    dataset_fingerprint_v2,
)
from backend.market_data.ingestion import NATIVE_M15_CONTRACT_V1
from backend.persistence.database import configure_utc_session_timezone
from backend.persistence.market_data_repository import (
    BarBatchItem,
    DatasetSnapshotRepository,
    MarketDataRepository,
)
from backend.persistence.models import (
    DatasetSnapshotAnalyticalBarModel,
    DatasetSnapshotExecutionObservationModel,
    DatasetSnapshotModel,
    ExperimentAccountModel,
    ExperimentEquityPointModel,
    ExperimentModel,
    ExperimentResultModel,
    FillModel,
    MarketBarModel,
    OrderModel,
    PositionModel,
    RiskDecisionModel,
    TradeIntentModel,
    TradeModel,
)
from backend.persistence.strategy_repository import StrategyRepository
from backend.strategies.candle_confirmation_break import (
    CANDLE_CONFIRMATION_BREAK_EVIDENCE_SCHEMA,
    CandleConfirmationBreakStrategy,
)
from backend.strategies.fingerprint import archive_source
from backend.strategies.production import create_production_strategy_registry
from backend.tests.integration.test_golden_flows import (
    ROOT,
    START,
    _golden_bars,  # pyright: ignore[reportPrivateUsage]
    _native_m15_bars,  # pyright: ignore[reportPrivateUsage]
)

pytestmark = pytest.mark.integration

PARAMETERS = {
    "confirmation_bars": 1,
    "stop_buffer_pips": "20",
    "target_r": "1.5",
}


@pytest.fixture(scope="module")
def database_url() -> str:
    value = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not value:
        pytest.skip("ATLAS_TEST_DATABASE_URL is required for candidate flow")
    return value


def _seed_candidate(session: Session) -> tuple[UUID, UUID]:
    venue = MarketDataRepository().ensure_initial_venue_instrument(
        session, VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD")
    )
    bars = _golden_bars("LONG")
    retrieved = START + timedelta(days=1)
    MarketDataRepository().apply_bar_batch(
        session,
        venue.id,
        tuple(BarBatchItem(bar, retrieved, "candidate-long") for bar in bars),
    )
    native = _native_m15_bars("LONG")
    stored_bars = {
        (row.start_time, row.price_component): row
        for row in session.scalars(
            select(MarketBarModel).where(MarketBarModel.venue_instrument_id == venue.id)
        ).all()
    }
    execution_times = {
        START + timedelta(minutes=1530),
        START + timedelta(minutes=1545),
        START + timedelta(minutes=1559),
    }
    execution = tuple(
        (stored_bars[(bar.start_time, bar.price_component.value)], bar)
        for bar in bars
        if bar.start_time in execution_times
    )
    metadata = {
        "provider": "OANDA",
        "instrument": "EUR/USD",
        "coverage_start": START.isoformat(),
        "coverage_end": (START + timedelta(minutes=1560)).isoformat(),
        "native_resolution": "M15",
        "analytical_contract": NATIVE_M15_CONTRACT_V1,
        "gap_policy": GAP_POLICY_V1,
    }
    analytical_members = tuple(
        {
            "sequence": sequence,
            "start_time": bar.start_time.isoformat(),
            "end_time": bar.end_time.isoformat(),
            "content_fingerprint": bar_content_fingerprint(bar),
        }
        for sequence, bar in enumerate(native, 1)
    )
    execution_members = tuple(
        {
            "sequence": sequence,
            "market_bar_id": str(row.id),
            "price_component": bar.price_component.value,
            "start_time": bar.start_time.isoformat(),
            "observation_fingerprint": bar_content_fingerprint(bar),
        }
        for sequence, (row, bar) in enumerate(execution, 1)
    )
    snapshot = DatasetSnapshot(
        id=uuid4(),
        venue_instrument=VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        base_resolution=Timeframe.M15,
        components=(PriceComponent.MID,),
        coverage_start=START,
        coverage_end=START + timedelta(minutes=1560),
        alignment_convention=ALIGNMENT_CONVENTION,
        session_policy=SESSION_POLICY,
        fingerprint_schema=FINGERPRINT_SCHEMA_V2,
        fingerprint=dataset_fingerprint_v2(
            metadata=metadata,
            analytical_members=analytical_members,
            execution_members=execution_members,
            gaps=(),
        ),
        integrity_summary={
            "status": "VALID",
            "policy_version": GAP_POLICY_V1,
            "analytical_count": len(native),
            "execution_count": len(execution),
            "gap_count": 0,
            "analytical_contract": NATIVE_M15_CONTRACT_V1,
        },
        created_at=START + timedelta(days=1),
        snapshot_schema="ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2",
    )
    snapshot_row = DatasetSnapshotRepository().create_v2_validated(
        session, snapshot, native, execution, ()
    )
    MarketDataRepository().record_acquisition_window(
        session,
        venue.id,
        Timeframe.M1,
        (PriceComponent.ASK, PriceComponent.BID),
        START + timedelta(minutes=1500),
        START + timedelta(minutes=1560),
        "SUCCESS_EMPTY_OR_SPARSE",
        returned_count=3,
    )
    archive = archive_source(ROOT, CandleConfirmationBreakStrategy.definition.source_files)
    version = StrategyVersion(
        id=uuid4(),
        strategy_key=CandleConfirmationBreakStrategy.definition.strategy_key,
        version_number=1,
        source_fingerprint=archive.fingerprint,
        implementation_key=CandleConfirmationBreakStrategy.definition.implementation_key,
        parameter_schema=CandleConfirmationBreakStrategy.definition.parameter_schema,
        primary_timeframe=Timeframe.M15,
        required_historical_context_bars=1,
        state_schema_version=1,
        created_at=START,
    )
    version_row = StrategyRepository().create_version(
        session,
        version,
        strategy_name=CandleConfirmationBreakStrategy.definition.name,
        strategy_description=CandleConfirmationBreakStrategy.definition.description,
        capabilities=CandleConfirmationBreakStrategy.definition.capabilities,
        source_archive=archive,
    )
    return snapshot_row.id, version_row.id


def test_candidate_persisted_v2_flow_preserves_generic_lineage(database_url: str) -> None:
    engine = configure_utc_session_timezone(create_engine(database_url))
    registry = create_production_strategy_registry(ROOT)
    try:
        with Session(engine) as session, session.begin():
            snapshot_id, version_id = _seed_candidate(session)
            configuration = ExperimentConfigurationService(registry)
            request_parameters = dict(PARAMETERS)
            experiment = configuration.create(
                session,
                strategy_version_id=version_id,
                dataset_snapshot_id=snapshot_id,
                trading_start=START + timedelta(minutes=1500),
                trading_end=START + timedelta(minutes=1560),
                starting_capital=Decimal("10000"),
                risk_per_trade=Decimal("0.01"),
                parameters=request_parameters,
                slippage_ticks=0,
                commission_per_unit=Decimal("0"),
            )
            experiment_id = experiment.id
            request_parameters["stop_buffer_pips"] = "99"
            assert experiment.parameter_snapshot == {
                "confirmation_bars": 1,
                "stop_buffer_pips": "20",
                "target_r": "1.5",
            }

        runner = ExperimentRunner(strategy_registry=registry)
        lifecycle = ExperimentRunService(lambda: Session(engine), runner)
        run_result = lifecycle.run(experiment_id)
        assert run_result.status == "COMPLETED", run_result.failure
        assert run_result.trade_completed

        with Session(engine) as session:
            experiment = session.get(ExperimentModel, experiment_id)
            assert experiment is not None
            assert experiment.status == "COMPLETED"
            assert experiment.parameter_snapshot == {
                "confirmation_bars": 1,
                "stop_buffer_pips": "20",
                "target_r": "1.5",
            }
            snapshot = session.get(DatasetSnapshotModel, snapshot_id)
            assert snapshot is not None
            assert snapshot.snapshot_schema == "ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2"
            assert snapshot.base_resolution == "M15"
            assert snapshot.components == ["MID"]
            last_analytical = session.scalar(
                select(DatasetSnapshotAnalyticalBarModel).where(
                    DatasetSnapshotAnalyticalBarModel.dataset_snapshot_id == snapshot_id
                ).order_by(DatasetSnapshotAnalyticalBarModel.sequence.desc())
            )
            assert last_analytical is not None
            assert last_analytical.sequence == 104
            execution_rows = session.scalars(
                select(DatasetSnapshotExecutionObservationModel).where(
                    DatasetSnapshotExecutionObservationModel.dataset_snapshot_id == snapshot_id
                ).order_by(DatasetSnapshotExecutionObservationModel.start_time)
            ).all()
            assert len(execution_rows) == 6
            assert {row.price_component for row in execution_rows} == {"BID", "ASK"}

            intent = session.scalar(
                select(TradeIntentModel).where(TradeIntentModel.experiment_id == experiment_id)
            )
            assert intent is not None
            assert intent.action == "OPEN_LONG"
            assert intent.entry_policy == "IMMEDIATE"
            assert intent.decision_frontier == START + timedelta(minutes=1530)
            assert intent.proposed_stop == Decimal("1.0960")
            expected_evidence = {
                "schema_key": CANDLE_CONFIRMATION_BREAK_EVIDENCE_SCHEMA,
                "version": 1,
                "fields": {
                    "direction": "LONG",
                    "prior_timestamp": (START + timedelta(minutes=1515)).isoformat().replace("+00:00", "Z"),
                    "prior_open": "1.1020000000",
                    "prior_high": "1.1030000000",
                    "prior_low": "1.0995000000",
                    "prior_close": "1.1010000000",
                    "signal_timestamp": (START + timedelta(minutes=1530)).isoformat().replace("+00:00", "Z"),
                    "signal_open": "1.1000000000",
                    "signal_high": "1.1040000000",
                    "signal_low": "1.0980000000",
                    "signal_close": "1.1035000000",
                    "confirmation_count": 1,
                    "confirmation_bars": 1,
                    "pip_size": "0.0001",
                    "stop_buffer_pips": "20",
                    "proposed_stop": "1.0960000000",
                    "target_multiple": "1.5",
                },
            }
            assert intent.rationale["evidence"] == expected_evidence

            risks = session.scalars(
                select(RiskDecisionModel).where(
                    RiskDecisionModel.trade_intent_id == intent.id
                ).order_by(RiskDecisionModel.evaluated_at, RiskDecisionModel.phase)
            ).all()
            assert [(risk.phase, risk.outcome) for risk in risks] == [
                ("PRE_FLIGHT", "APPROVED"),
                ("PRE_SUBMISSION", "APPROVED"),
            ]
            assert risks[1].stop_price == intent.proposed_stop

            orders = session.scalars(
                select(OrderModel).where(OrderModel.trade_intent_id == intent.id).order_by(OrderModel.created_at, OrderModel.purpose)
            ).all()
            assert {order.purpose for order in orders} == {"ENTRY", "STOP_LOSS", "TAKE_PROFIT", "EXIT"}
            assert all(order.risk_decision_id == risks[1].id for order in orders)
            fills = session.scalars(
                select(FillModel).join(OrderModel).where(OrderModel.experiment_id == experiment_id).order_by(FillModel.executed_at)
            ).all()
            assert len(fills) == 2
            entry_fill = next(fill for fill in fills if fill.order_id == next(order.id for order in orders if order.purpose == "ENTRY"))
            source = session.get(MarketBarModel, entry_fill.source_market_bar_id)
            assert source is not None
            assert source.price_component == "ASK"
            assert entry_fill.executed_at > intent.decision_frontier
            assert entry_fill.executed_at == START + timedelta(minutes=1545)
            assert entry_fill.execution_price == risks[1].entry_price

            trade = session.scalar(select(TradeModel).where(TradeModel.experiment_id == experiment_id))
            account = session.get(ExperimentAccountModel, experiment_id)
            position = session.scalar(select(PositionModel).where(PositionModel.experiment_id == experiment_id))
            result = session.get(ExperimentResultModel, experiment_id)
            equity = session.scalars(
                select(ExperimentEquityPointModel).where(
                    ExperimentEquityPointModel.experiment_id == experiment_id
                ).order_by(ExperimentEquityPointModel.sequence_number)
            ).all()
            assert trade is not None and account is not None and position is not None and result is not None
            assert trade.trade_intent_id == intent.id
            assert trade.status == "COMPLETED"
            assert trade.exit_order_id is not None
            assert position.state == "FLAT"
            assert account.equity == result.ending_equity
            assert result.trade_count == 1
            assert equity and equity[-1].equity == account.equity

            reader = ExperimentResultReadService()
            detail = reader.detail(session, experiment_id)
            inspected_trade = reader.trade(session, experiment_id, 1)
            price_analysis = reader.price_analysis(session, experiment_id)
            assert detail["result"] is not None
            assert inspected_trade["evidence"] == expected_evidence
            assert inspected_trade["initial_stop"] == Decimal("1.0960")
            assert inspected_trade["setupFacts"] is None
            assert price_analysis.provenance["analyticalSeries"] == "PERSISTED_NATIVE_M15_MID"
            assert price_analysis.provenance["executionSeries"] == "SPARSE_PROVIDER_M1_BID_ASK"
            assert price_analysis.evidence == (
                {"trade_sequence": 1, "setup": expected_evidence},
            )
    finally:
        engine.dispose()
