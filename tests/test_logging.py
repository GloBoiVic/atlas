import json

import structlog

from backend.core.logging import setup_logging


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
