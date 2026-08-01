import json

import pytest
import structlog

from backend.core.logging import setup_logging
from backend.health.circuit_breaker import CircuitBreaker


def test_setup_logging_emits_structured_json_with_context_and_error(capsys) -> None:
    setup_logging()
    logger = structlog.get_logger("logging-test")

    try:
        raise ValueError("invalid order")
    except ValueError:
        logger.exception("order_failed", order_id="order-123")

    record = json.loads(capsys.readouterr().err)

    assert record["event"] == "order_failed"
    assert record["order_id"] == "order-123"
    assert record["level"] == "error"
    assert "timestamp" in record
    assert "exception" in record


@pytest.mark.asyncio
async def test_circuit_breaker_logs_only_approved_context(capsys) -> None:
    setup_logging()
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=10,
        context={"account_id": "account-123", "api_token": "secret-token"},
    )

    async def fail() -> None:
        raise RuntimeError("dependency failed")

    with pytest.raises(RuntimeError):
        await breaker.call(fail)

    rendered_logs = capsys.readouterr().err

    assert '"account_id": "account-123"' in rendered_logs
    assert "api_token" not in rendered_logs
    assert "secret-token" not in rendered_logs
