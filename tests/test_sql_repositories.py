from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql

from backend.persistence.repositories.protocols import ReconciliationRecord
from backend.persistence.repositories.sqlalchemy import (
    _claim_statement,
    _reconciliation_insert_statement,
)


def compile_postgresql(statement: object) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_claim_uses_atomic_upsert_and_stale_lease_predicate():
    sql = compile_postgresql(
        _claim_statement("bot-1", "worker-a", datetime(2026, 8, 1, 12, 0, tzinfo=UTC))
    )

    assert "ON CONFLICT (bot_id) DO UPDATE" in sql
    assert "locked_at <=" in sql
    assert "RETURNING" in sql


def test_reconciliation_insert_uses_database_conflict_idempotency():
    result = ReconciliationRecord(
        id="reconciliation-1",
        account_id="account-1",
        bot_id="bot-1",
        status="matched",
    )

    sql = compile_postgresql(_reconciliation_insert_statement(result))

    assert "ON CONFLICT (id) DO NOTHING" in sql
    assert "RETURNING" in sql
