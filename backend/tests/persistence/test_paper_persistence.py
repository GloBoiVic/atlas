from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from backend.persistence.lifecycle_locks import deployment_advisory_lock_key
from backend.persistence.models import (
    AccountTransactionCursorModel,
    DeploymentFrontierModel,
)
from backend.persistence.paper_repository import (
    DeploymentRepository,
    PendingEntryRepository,
    SafetyRepository,
    TradingAccountRepository,
    stable_client_correlation_id,
)
from backend.persistence.trading_repository import TradingRepository
from backend.risk import RiskDecision, RiskPhase

UTC_NOW = datetime(2026, 1, 1, tzinfo=UTC)
NON_UTC = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=1)))
DEPLOYMENT_ID = UUID(int=1)


class _FakeSession:
    def __init__(self, row: object) -> None:
        self.row = row

    def scalar(self, _statement: object) -> object:
        return self.row

    def add(self, _row: object) -> None:
        pass

    def flush(self) -> None:
        pass


def test_deployment_lock_key_and_client_correlation_are_stable() -> None:
    deployment_id = UUID("00000000-0000-0000-0000-000000000001")

    assert deployment_advisory_lock_key(deployment_id) == deployment_advisory_lock_key(
        deployment_id
    )
    assert 0 < deployment_advisory_lock_key(deployment_id) < 2**63
    assert stable_client_correlation_id(deployment_id).endswith(str(deployment_id))


def test_trading_repository_rejects_rootless_and_dual_owned_facts() -> None:
    repository = TradingRepository()
    values = {
        "strategy_version_id": UUID(int=1),
        "venue_instrument_id": UUID(int=2),
        "decision_frontier": datetime.now(UTC),
        "action": "OPEN_LONG",
        "direction": "LONG",
        "proposed_stop": None,
        "target_multiple": None,
        "rationale": {},
    }

    with pytest.raises(ValueError, match="exactly one root"):
        repository.create_intent(None, **values)
    with pytest.raises(ValueError, match="exactly one root"):
        repository.create_intent(
            None,
            experiment_id=UUID(int=3),
            deployment_id=UUID(int=4),
            **values,
        )


def test_account_repository_rejects_secret_bearing_evidence() -> None:
    with pytest.raises(ValueError, match="secret-bearing"):
        TradingAccountRepository().create(
            None,
            label="Practice",
            external_account_id="101-001",
            provenance={"access_token": "must-not-persist"},
        )


def test_deployment_repository_requires_immutable_snapshots() -> None:
    with pytest.raises(ValueError, match="immutable"):
        DeploymentRepository().create(
            None,
            trading_account_id=UUID(int=1),
            strategy_version_id=UUID(int=2),
            venue_instrument_id=UUID(int=3),
            parameter_snapshot={},
            risk_snapshot={},
        )


@pytest.mark.parametrize("timestamp", [datetime(2026, 1, 1), NON_UTC])
def test_paper_timestamp_boundaries_reject_naive_and_non_utc(
    timestamp: datetime,
) -> None:
    decision = RiskDecision(phase=RiskPhase.PRE_FLIGHT, approved=False)
    intent_values = {
        "strategy_version_id": UUID(int=2),
        "venue_instrument_id": UUID(int=3),
        "decision_frontier": timestamp,
        "action": "OPEN_LONG",
        "direction": "LONG",
        "proposed_stop": None,
        "target_multiple": None,
        "rationale": {},
    }

    operations = (
        lambda: DeploymentRepository().mark_first_trade(None, DEPLOYMENT_ID, timestamp),
        lambda: PendingEntryRepository().transition(
            None, DEPLOYMENT_ID, "FILLED", resolved_at=timestamp
        ),
        lambda: SafetyRepository().record_frontier(
            None,
            DEPLOYMENT_ID,
            completed_m15_frontier=timestamp,
            completed_m15_fingerprint="a" * 64,
        ),
        lambda: SafetyRepository().record_frontier(
            None, DEPLOYMENT_ID, last_execution_observation_at=timestamp
        ),
        lambda: SafetyRepository().record_account_snapshot(
            None, observed_at=timestamp
        ),
        lambda: SafetyRepository().record_heartbeat(None, observed_at=timestamp),
        lambda: SafetyRepository().record_system_event(
            None, detail="heartbeat", occurred_at=timestamp
        ),
        lambda: SafetyRepository().record_reconciliation(
            None, started_at=timestamp, finished_at=UTC_NOW
        ),
        lambda: SafetyRepository().record_reconciliation(
            None, started_at=UTC_NOW, finished_at=timestamp
        ),
        lambda: SafetyRepository().advance_cursor(
            None,
            trading_account_id=UUID(int=4),
            last_transaction_id="1",
            observed_at=timestamp,
            source="test",
        ),
        lambda: TradingRepository().create_paper_risk_decision(
            None, trade_intent_id=UUID(int=5), decision=decision, evaluated_at=timestamp
        ),
        lambda: TradingRepository().create_intent(
            None, deployment_id=DEPLOYMENT_ID, **intent_values
        ),
        lambda: TradingRepository().create_intent(
            None,
            deployment_id=DEPLOYMENT_ID,
            **{**intent_values, "decision_frontier": UTC_NOW, "expiry_time": timestamp},
        ),
    )

    for operation in operations:
        with pytest.raises(ValueError, match="timezone-aware UTC"):
            operation()


def test_paper_risk_decision_rejects_non_utc_quote_observation() -> None:
    decision = RiskDecision(
        phase=RiskPhase.PRE_FLIGHT, approved=False, quote_observed_at=NON_UTC
    )

    with pytest.raises(
        ValueError, match="quote_observed_at must be timezone-aware UTC"
    ):
        TradingRepository().create_paper_risk_decision(
            None,
            trade_intent_id=UUID(int=5),
            decision=decision,
            evaluated_at=UTC_NOW,
        )


def test_frontier_and_cursor_accept_utc_and_preserve_monotonicity() -> None:
    frontier_row = DeploymentFrontierModel(
        deployment_id=DEPLOYMENT_ID,
        completed_m15_frontier=UTC_NOW,
        completed_m15_fingerprint="a" * 64,
        last_execution_observation_at=UTC_NOW,
        source="test",
    )
    frontier_session = _FakeSession(frontier_row)
    later = UTC_NOW + timedelta(minutes=15)

    updated = SafetyRepository().record_frontier(
        frontier_session, DEPLOYMENT_ID,
        completed_m15_frontier=later,
        completed_m15_fingerprint="b" * 64,
        last_execution_observation_at=later,
    )

    assert updated.completed_m15_frontier == later
    assert updated.last_execution_observation_at == later
    with pytest.raises(
        ValueError, match="completed-M15 frontier cannot move backwards"
    ):
        SafetyRepository().record_frontier(
            frontier_session,
            DEPLOYMENT_ID,
            completed_m15_frontier=UTC_NOW,
            completed_m15_fingerprint="a" * 64,
        )

    cursor_row = AccountTransactionCursorModel(
        trading_account_id=UUID(int=4),
        last_transaction_id="10",
        observed_at=UTC_NOW,
        source="test",
    )
    cursor_session = _FakeSession(cursor_row)
    with pytest.raises(ValueError, match="transaction cursor cannot move backwards"):
        SafetyRepository().advance_cursor(
            cursor_session,
            trading_account_id=UUID(int=4),
            last_transaction_id="9",
            observed_at=later,
            source="test",
        )
    with pytest.raises(
        ValueError,
        match="transaction cursor observation cannot move backwards",
    ):
        SafetyRepository().advance_cursor(
            cursor_session,
            trading_account_id=UUID(int=4),
            last_transaction_id="10",
            observed_at=UTC_NOW - timedelta(seconds=1),
            source="test",
        )
