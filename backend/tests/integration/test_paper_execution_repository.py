"""Deterministic PostgreSQL evidence for the PAPER persistence foundation."""

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from os import environ
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.domain import (
    Instrument,
    Provider,
    StrategyEvaluation,
    StrategyState,
    StrategyVersion,
    ValidatedParameterPayload,
)
from backend.paper import (
    BrokerFillFacts,
    BrokerProtectionOrder,
    BrokerUncertainty,
    ExecutionAccountIdentity,
    ExecutionCorrelation,
    ExecutionObservationProvenance,
    PaperBrokerObservation,
    PaperExecutionAttempt,
    PaperExecutionInstruction,
    PaperExecutionOutcome,
    PaperExecutionResult,
    PaperMutationPhase,
    PaperObservationObjectKind,
    PaperObservationReadKind,
    PaperReconciliationRun,
    PaperReconciliationRunStatus,
    PaperRiskAuthoritySnapshot,
    PaperStrategyEvaluationReceipt,
    ProtectionConfirmation,
    ProtectionLegStatus,
    ReconciliationStatus,
    TransactionProvenance,
)
from backend.persistence.database import (
    configure_utc_session_timezone,
    create_session_factory,
)
from backend.persistence.models import (
    PaperBrokerObservationModel,
    PaperExecutionAttemptModel,
    PaperMutationClaimModel,
    StrategyModel,
    StrategyVersionModel,
)
from backend.persistence.paper_execution_repository import (
    DuplicateMutationClaim,
    InvalidPaperTransition,
    PaperExecutionRepository,
    PaperIdentityConflict,
    StaleReconciliationError,
)
from backend.risk import RiskConfig
from backend.tests.paper.test_risk_evaluation import evaluate, opening

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)
VERSION_ID = UUID("11111111-1111-1111-1111-111111111111")
ATTEMPT_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def paper_database() -> Generator[Engine]:
    value = environ.get("ATLAS_TEST_DATABASE_URL")
    if not value or not value.rsplit("/", 1)[-1].endswith("_test"):
        pytest.skip("ATLAS_TEST_DATABASE_URL must name a dedicated *_test database")
    engine = configure_utc_session_timezone(create_engine(value))
    yield engine
    engine.dispose()


def _attempt() -> PaperExecutionAttempt:
    decision = opening()
    risk = evaluate(decision)
    assert decision.direction is not None
    assert decision.decision_time is not None
    assert risk.pre_flight is not None
    assert risk.pre_submission is not None
    assert risk.pre_submission.quantity is not None
    assert risk.pre_submission.entry_price is not None
    assert risk.pre_submission.stop_price is not None
    assert risk.provenance is not None
    assert risk.pricing_evidence is not None
    assert risk.trade_intent is not None
    account = ExecutionAccountIdentity(
        Provider.OANDA, "PRACTICE", "001-011-5838423-001", "USD"
    )
    instruction = PaperExecutionInstruction(
        attempt_id=ATTEMPT_ID,
        strategy_decision=decision,
        account=account,
        instrument=Instrument.EUR_USD,
        direction=decision.direction,
        requested_quantity=risk.pre_submission.quantity,
        approved_entry_price=risk.pre_submission.entry_price,
        stop_price=risk.pre_submission.stop_price,
        decision_time=decision.decision_time,
        pricing_time=risk.provenance.price_time,
        pre_flight=risk.pre_flight,
        pre_submission=risk.pre_submission,
        observation_provenance=ExecutionObservationProvenance(
            account,
            risk.provenance.summary_last_transaction_id,
            risk.provenance.price_time,
            "13",
        ),
        display_precision=5,
        trade_units_precision=0,
    )
    version = StrategyVersion(
        id=VERSION_ID,
        strategy_key="paper_fixture",
        version_number=1,
        source_fingerprint="a" * 64,
        implementation_key="paper_fixture.v1",
        parameter_schema=(),
        created_at=NOW,
    )
    receipt = PaperStrategyEvaluationReceipt.from_verified(
        version,
        ValidatedParameterPayload.from_mapping((), {}),
        StrategyEvaluation(decision, StrategyState()),
    )
    authority = PaperRiskAuthoritySnapshot.from_evaluation(
        risk,
        config=RiskConfig(Decimal("0.01")),
        account_equity=Decimal("10000"),
    )
    return PaperExecutionAttempt(receipt, authority, instruction)


def _seed_strategy(session: Session) -> None:
    strategy = StrategyModel(
        id=uuid4(),
        strategy_key="paper_fixture",
        name="PAPER fixture",
        description="PAPER persistence fixture",
    )
    session.add(strategy)
    session.add(
        StrategyVersionModel(
            id=VERSION_ID,
            strategy_id=strategy.id,
            version_number=1,
            source_fingerprint="a" * 64,
            implementation_key="paper_fixture.v1",
            parameter_schema=[],
            context_timeframes=[],
            capabilities=[],
            source_manifest=[],
            exact_source_snapshot={},
            primary_timeframe="15m",
            required_historical_context_bars=0,
            state_schema_version=1,
            strategy=strategy,
        )
    )
    session.flush()


def test_claim_is_permanent_and_fill_is_not_erased(paper_database: Engine) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()
    attempt = _attempt()
    with factory() as session:
        _seed_strategy(session)
        claim = repository.commit_entry_claim(
            session,
            attempt,
            provider_endpoint_key="OANDA_ENTRY_POST",
            normalized_request_fingerprint="b" * 64,
        )
        assert claim.phase == PaperMutationPhase.ENTRY.value
    with factory() as session:
        assert repository.get_attempt(session, ATTEMPT_ID) is not None
    with factory.begin() as session:
        with pytest.raises(DuplicateMutationClaim):
            repository.claim_mutation(
                session,
                ATTEMPT_ID,
                phase=PaperMutationPhase.ENTRY,
                provider_endpoint_key="OANDA_ENTRY_POST",
                normalized_request_fingerprint="b" * 64,
            )

    changed_pre_submission = replace(
        attempt.instruction.pre_submission,
        quantity=attempt.instruction.requested_quantity + Decimal("1"),
    )
    changed_instruction = replace(
        attempt.instruction,
        requested_quantity=attempt.instruction.requested_quantity + Decimal("1"),
        pre_submission=changed_pre_submission,
    )
    changed_authority = replace(
        attempt.risk_authority,
        pre_submission=changed_pre_submission,
    )
    changed_attempt = PaperExecutionAttempt(
        attempt.receipt, changed_authority, changed_instruction
    )
    with factory.begin() as session:
        with pytest.raises(PaperIdentityConflict):
            repository.create_attempt(session, changed_attempt)

    fill = BrokerFillFacts(
        "order-42",
        "transaction-43",
        "trade-44",
        Decimal("1000"),
        Decimal("1.1"),
        NOW,
        Decimal("50"),
    )
    with factory.begin() as session:
        repository.record_fill(session, ATTEMPT_ID, fill)
        repository.apply_execution_outcome(
            session, ATTEMPT_ID, PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE
        )
    with factory.begin() as session:
        with pytest.raises(InvalidPaperTransition):
            repository.apply_execution_outcome(
                session, ATTEMPT_ID, PaperExecutionOutcome.UNKNOWN
            )
    with factory() as session:
        row = repository.get_attempt(session, ATTEMPT_ID)
        assert row is not None
        assert row.fill_trade_id == "trade-44"
        assert (
            row.execution_outcome
            == PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE.value
        )


def test_caller_owned_entry_claim_rollback_leaves_no_paper_authority(
    paper_database: Engine,
) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()

    with factory() as session:
        with pytest.raises(RuntimeError, match="runtime transaction failed"):
            with session.begin():
                _seed_strategy(session)
                claim = repository.persist_entry_claim(
                    session,
                    _attempt(),
                    provider_endpoint_key="OANDA_ENTRY_POST",
                    normalized_request_fingerprint="b" * 64,
                )
                assert claim.phase == PaperMutationPhase.ENTRY.value
                raise RuntimeError("runtime transaction failed")

    with factory() as session:
        assert repository.get_attempt(session, ATTEMPT_ID) is None
        assert (
            session.scalar(
                select(PaperMutationClaimModel).where(
                    PaperMutationClaimModel.attempt_id == ATTEMPT_ID
                )
            )
            is None
        )


def test_observation_replay_is_idempotent(paper_database: Engine) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()
    attempt = _attempt()
    with factory.begin() as session:
        _seed_strategy(session)
        repository.create_attempt(session, attempt)
    observation = PaperBrokerObservation(
        attempt_id=ATTEMPT_ID,
        read_kind=PaperObservationReadKind.ORDER_DETAIL,
        object_kind=PaperObservationObjectKind.ORDER,
        provider_account_id="001-011-5838423-001",
        instrument=Instrument.EUR_USD,
        normalized_facts={"order_id": "42", "state": "PENDING"},
        provider_order_id="42",
        atlas_observed_at=NOW,
    )
    with factory.begin() as session:
        first = repository.append_observation(session, observation)
        second = repository.append_observation(session, observation)
        assert first.observation_id == second.observation_id
        assert (
            session.scalar(
                select(func.count(PaperBrokerObservationModel.observation_id)).where(
                    PaperBrokerObservationModel.attempt_id == ATTEMPT_ID
                )
            )
            == 1
        )


def test_same_id_result_conflict_leaves_projection_unchanged(
    paper_database: Engine,
) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()
    attempt = _attempt()
    with factory.begin() as session:
        _seed_strategy(session)
        repository.create_attempt(session, attempt)

    changed_pre_submission = replace(
        attempt.instruction.pre_submission,
        quantity=attempt.instruction.requested_quantity + Decimal("1"),
    )
    changed_instruction = replace(
        attempt.instruction,
        requested_quantity=attempt.instruction.requested_quantity + Decimal("1"),
        pre_submission=changed_pre_submission,
    )
    result = PaperExecutionResult(
        outcome=PaperExecutionOutcome.UNKNOWN,
        instruction=changed_instruction,
        correlation=ExecutionCorrelation.for_attempt(ATTEMPT_ID),
        fill=None,
        protection=ProtectionConfirmation(
            ProtectionLegStatus.NOT_ATTEMPTED,
            None,
            ProtectionLegStatus.NOT_ATTEMPTED,
            None,
            None,
        ),
        rejection=None,
        uncertainty=BrokerUncertainty("RESULT_UNCERTAIN"),
        transaction_provenance=TransactionProvenance(),
    )
    with factory() as session:
        with pytest.raises(PaperIdentityConflict):
            repository.apply_result(session, result)
        session.commit()

    with factory() as session:
        row = repository.get_attempt(session, ATTEMPT_ID)
        assert row is not None
        assert row.requested_quantity == Decimal("20000.0000000000")
        assert row.execution_outcome is None


def test_unattributed_protection_is_rejected_without_advancing_outcome(
    paper_database: Engine,
) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()
    attempt = _attempt()
    fill = BrokerFillFacts(
        "order-42",
        "transaction-43",
        "trade-44",
        Decimal("1000"),
        Decimal("1.1"),
        NOW,
        Decimal("50"),
    )
    with factory.begin() as session:
        _seed_strategy(session)
        repository.create_attempt(session, attempt)
        repository.apply_execution_outcome(
            session,
            ATTEMPT_ID,
            PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE,
            fill=fill,
        )

    unrelated = ProtectionConfirmation(
        ProtectionLegStatus.CONFIRMED,
        BrokerProtectionOrder(
            "unrelated-stop",
            "unrelated-stop-client",
            Decimal("9.98"),
            "PENDING",
        ),
        ProtectionLegStatus.CONFIRMED,
        BrokerProtectionOrder(
            "unrelated-tp",
            "unrelated-tp-client",
            Decimal("9.98"),
            "PENDING",
        ),
        Decimal("9.98"),
    )
    with factory() as session:
        with pytest.raises(PaperIdentityConflict):
            repository.apply_protection(session, ATTEMPT_ID, unrelated)
        session.commit()

    with factory() as session:
        row = repository.get_attempt(session, ATTEMPT_ID)
        assert row is not None
        assert (
            row.execution_outcome
            == PaperExecutionOutcome.FILLED_PROTECTION_INCOMPLETE.value
        )
        assert row.fill_trade_id == "trade-44"
        assert row.stop_loss_status == ProtectionLegStatus.NOT_ATTEMPTED.value
        assert row.take_profit_status == ProtectionLegStatus.NOT_ATTEMPTED.value
        assert row.actual_target_price is None


def test_exact_protection_reaches_filled_protected(
    paper_database: Engine,
) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()
    attempt = _attempt()
    fill = BrokerFillFacts(
        "order-42",
        "transaction-43",
        "trade-44",
        Decimal("1000"),
        Decimal("1.1"),
        NOW,
        Decimal("50"),
    )
    protection = ProtectionConfirmation(
        ProtectionLegStatus.CONFIRMED,
        BrokerProtectionOrder(
            "stop-45",
            attempt.correlation.client_stop_loss_order_id,
            Decimal("1.0950"),
            "PENDING",
        ),
        ProtectionLegStatus.CONFIRMED,
        BrokerProtectionOrder(
            "take-profit-46",
            attempt.correlation.client_take_profit_order_id,
            Decimal("1.1085"),
            "PENDING",
        ),
        Decimal("1.1085"),
    )
    with factory.begin() as session:
        _seed_strategy(session)
        repository.create_attempt(session, attempt)
        repository.record_fill(session, ATTEMPT_ID, fill)
        repository.apply_protection(session, ATTEMPT_ID, protection)
        row = repository.apply_execution_outcome(
            session,
            ATTEMPT_ID,
            PaperExecutionOutcome.FILLED_PROTECTED,
            protection=protection,
        )
        assert row.execution_outcome == PaperExecutionOutcome.FILLED_PROTECTED.value

    changed_broker_id = replace(
        protection,
        stop_loss=replace(
            protection.stop_loss
            if protection.stop_loss is not None
            else BrokerProtectionOrder("missing", "missing", Decimal("1"), "PENDING"),
            broker_order_id="unrelated-stop",
        ),
    )
    with factory() as session:
        with pytest.raises(PaperIdentityConflict):
            repository.apply_protection(session, ATTEMPT_ID, changed_broker_id)
        session.commit()

    with factory() as session:
        row = repository.get_attempt(session, ATTEMPT_ID)
        assert row is not None
        assert row.execution_outcome == PaperExecutionOutcome.FILLED_PROTECTED.value
        assert row.stop_loss_broker_order_id == "stop-45"
        assert row.take_profit_broker_order_id == "take-profit-46"
        assert row.actual_target_price == Decimal("1.1085000000")


def test_concurrent_entry_claims_have_one_winner(paper_database: Engine) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()
    attempt = _attempt()
    with factory.begin() as session:
        _seed_strategy(session)
        repository.create_attempt(session, attempt)

    start = Barrier(2)

    def claim() -> str:
        try:
            with factory.begin() as session:
                start.wait()
                repository.claim_entry(
                    session,
                    ATTEMPT_ID,
                    provider_endpoint_key="OANDA_ENTRY_POST",
                    normalized_request_fingerprint="c" * 64,
                )
            return "winner"
        except DuplicateMutationClaim:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(claim) for _ in range(2)]
        results = [future.result() for future in futures]
    assert sorted(results) == ["duplicate", "winner"]


def test_take_profit_claim_requires_durable_fill_and_protection(
    paper_database: Engine,
) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()
    attempt = _attempt()
    with factory.begin() as session:
        _seed_strategy(session)
        repository.create_attempt(session, attempt)
        repository.record_fill(
            session,
            ATTEMPT_ID,
            BrokerFillFacts(
                "order-42",
                "transaction-43",
                "trade-44",
                Decimal("1000"),
                Decimal("1.1"),
                NOW,
                Decimal("50"),
            ),
        )

    protection = ProtectionConfirmation(
        ProtectionLegStatus.CONFIRMED,
        BrokerProtectionOrder(
            "stop-45",
            attempt.correlation.client_stop_loss_order_id,
            Decimal("1.0950"),
            "PENDING",
        ),
        ProtectionLegStatus.CONFIRMED,
        BrokerProtectionOrder(
            "take-profit-46",
            attempt.correlation.client_take_profit_order_id,
            Decimal("1.1085"),
            "PENDING",
        ),
        Decimal("1.1085"),
    )
    with factory() as session:
        claim = repository.commit_take_profit_claim(
            session,
            ATTEMPT_ID,
            protection=protection,
            provider_endpoint_key="OANDA_TAKE_PROFIT_PUT",
            normalized_request_fingerprint="d" * 64,
        )
        assert claim.phase == PaperMutationPhase.TAKE_PROFIT.value
    with factory.begin() as session:
        with pytest.raises(DuplicateMutationClaim):
            repository.claim_take_profit(
                session,
                ATTEMPT_ID,
                provider_endpoint_key="OANDA_TAKE_PROFIT_PUT",
                normalized_request_fingerprint="d" * 64,
            )


def test_stale_reconciliation_cannot_advance_projection(
    paper_database: Engine,
) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()
    attempt = _attempt()
    with factory.begin() as session:
        _seed_strategy(session)
        repository.create_attempt(session, attempt)

    first_run = PaperReconciliationRun(
        attempt_id=ATTEMPT_ID,
        run_sequence=1,
        requested_at=NOW,
        read_started_at=NOW,
        completed_at=NOW,
        status=PaperReconciliationRunStatus.PROVEN,
        projection_version_observed=0,
        read_count=1,
        read_budget=1,
        prior_execution_outcome=None,
        resulting_execution_outcome=None,
    )
    with factory.begin() as session:
        repository.apply_reconciliation_run(
            session,
            first_run,
            reconciliation_status=ReconciliationStatus.CONSISTENT,
        )

    stale_run = replace(
        first_run,
        run_id=uuid4(),
        run_sequence=2,
        status=PaperReconciliationRunStatus.UNRESOLVED,
    )
    with factory() as session:
        with pytest.raises(StaleReconciliationError):
            repository.apply_reconciliation_run(
                session,
                stale_run,
                reconciliation_status=ReconciliationStatus.UNRESOLVED,
            )
        session.commit()
        row = repository.get_attempt(session, ATTEMPT_ID)
        assert row is not None
        assert row.projection_version == 1
        assert row.reconciliation_status == ReconciliationStatus.CONSISTENT.value


def test_database_guards_reject_evidence_mutation(
    paper_database: Engine,
) -> None:
    factory = create_session_factory(paper_database)
    repository = PaperExecutionRepository()
    attempt = _attempt()
    observation = PaperBrokerObservation(
        attempt_id=ATTEMPT_ID,
        read_kind=PaperObservationReadKind.ORDER_DETAIL,
        object_kind=PaperObservationObjectKind.ORDER,
        provider_account_id="001-011-5838423-001",
        instrument=Instrument.EUR_USD,
        normalized_facts={"order_id": "42", "state": "PENDING"},
        provider_order_id="42",
        atlas_observed_at=NOW,
    )
    with factory.begin() as session:
        _seed_strategy(session)
        repository.create_attempt(session, attempt)
        repository.append_observation(session, observation)

    with factory() as session:
        with pytest.raises(SQLAlchemyError):
            session.execute(
                update(PaperBrokerObservationModel)
                .where(
                    PaperBrokerObservationModel.observation_id
                    == observation.observation_id
                )
                .values(provider_state="DRIFT")
            )
        session.rollback()
        with pytest.raises(SQLAlchemyError):
            session.execute(
                update(PaperExecutionAttemptModel)
                .where(PaperExecutionAttemptModel.attempt_id == ATTEMPT_ID)
                .values(requested_quantity=Decimal("999"))
            )
        session.rollback()
