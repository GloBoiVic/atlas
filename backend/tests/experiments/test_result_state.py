from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.experiments.metric_contract import METRIC_STATE_KEYS
from backend.persistence.experiment_repository import ExperimentRepository


def test_metric_state_contract_covers_every_headline_metric() -> None:
    assert METRIC_STATE_KEYS == (
        "net_return",
        "max_drawdown_amount",
        "max_drawdown_percent",
        "sharpe_ratio",
        "profit_factor",
        "win_rate",
        "expectancy_net_pnl",
    )


def test_completion_requires_result_before_terminal_transition() -> None:
    experiment_id = uuid4()
    row = SimpleNamespace(id=experiment_id, status="RUNNING")

    class Session:
        def scalar(self, _query):
            return row

        def get(self, model, identifier):
            return None

        def flush(self):
            raise AssertionError("completion must fail before flush")

    with pytest.raises(ValueError, match="requires a persisted result"):
        ExperimentRepository().mark_completed(Session(), experiment_id, datetime.now(UTC))
