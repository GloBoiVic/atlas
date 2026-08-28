import ast
import inspect
import textwrap
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.domain.market_data import PriceComponent, Provider, Timeframe
from backend.experiments.configuration import (
    MODEL_VERSION,
    RISK_SCHEMA_VERSION,
    SIMULATION_SCHEMA_VERSION,
    ConfigurationError,
    ExperimentConfigurationService,
    _execution_bar,
    _execution_coverage_valid,
    _stream_v2_execution_coverage,
    risk_config,
    simulation_config,
)
from backend.strategies.production import create_production_strategy_registry


def test_configuration_derives_only_supported_phase4_assumptions() -> None:
    assert risk_config(Decimal("0.01")) == {
        "schema_version": RISK_SCHEMA_VERSION,
        "risk_per_trade": "0.01",
    }
    config = simulation_config(slippage_ticks=2, commission_per_unit=Decimal("0.10"))
    assert config == {
        "schema_version": SIMULATION_SCHEMA_VERSION,
        "execution_resolution": "M1",
        "analysis_component": "MID",
        "execution_components": ["BID", "ASK"],
        "spread_model": "DATASET_BID_ASK_EMBEDDED",
        "slippage_model": {
            "type": "ADVERSE_FIXED_TICKS",
            "ticks": 2,
            "tick_size": "0.00001",
        },
        "commission_model": {"type": "PER_FILL_PER_UNIT_USD", "amount": "0.10"},
        "financing_model": {"type": "EXCLUDED", "disclosure": "FINANCING EXCLUDED"},
        "intrabar_policy": "STOP_LOSS_ADVERSE_FIRST_V1",
        "target_fill_policy": "REQUESTED_PRICE_NO_IMPROVEMENT_V1",
        "end_policy": "FINAL_ELIGIBLE_M1_CLOSE_V1",
        "equity_sampling": "TRADING_START_AND_EACH_ELIGIBLE_M1_CLOSE_V1",
    }
    assert MODEL_VERSION == "PHASE5_HISTORICAL_EXECUTION_V2"


def test_configuration_rejects_negative_simulation_values_at_boundary() -> None:
    with pytest.raises(ConfigurationError):
        simulation_config(slippage_ticks=-1, commission_per_unit=Decimal("0"))


def test_execution_bar_normalization_preserves_canonical_constructor_contract() -> None:
    start = datetime(2026, 1, 5, tzinfo=UTC)
    bar = _execution_bar(
        SimpleNamespace(
            price_component="BID",
            start_time=start,
            end_time=start + timedelta(minutes=1),
            open_price=Decimal("1.1"),
            high_price=Decimal("1.2"),
            low_price=Decimal("1.0"),
            close_price=Decimal("1.15"),
            volume=None,
        )
    )
    assert bar.provider is Provider.OANDA
    assert bar.timeframe is Timeframe.M1
    assert bar.price_component is PriceComponent.BID


def test_sparse_execution_requires_provenance_and_rejects_one_sided_absence() -> None:
    minute = datetime(2026, 1, 5, tzinfo=UTC)
    window = SimpleNamespace(start_time=minute, end_time=minute + timedelta(minutes=1))
    fully_absent = SimpleNamespace(
        missing=(
            SimpleNamespace(
                start=minute,
                components=(PriceComponent.BID, PriceComponent.ASK),
            ),
        ),
        closure_anomalies=(), unexpected_observations=(),
    )
    one_sided = SimpleNamespace(
        missing=(SimpleNamespace(start=minute, components=(PriceComponent.BID,)),),
        closure_anomalies=(), unexpected_observations=(),
    )
    assert _execution_coverage_valid(fully_absent, (window,))
    assert not _execution_coverage_valid(fully_absent, ())
    assert not _execution_coverage_valid(one_sided, (window,))


class _StreamingRows:
    def __init__(self, rows):
        self.rows = rows
        self.batch_sizes = []

    def yield_per(self, batch_size):
        self.batch_sizes.append(batch_size)
        return iter(self.rows)


class _ExecutionSession:
    def __init__(self, rows):
        self.rows = _StreamingRows(rows)

    def execute(self, _statement):
        return self.rows


def _execution_event(
    start: datetime,
    end: datetime,
    event_kind: int,
    price_component: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        start_time=start,
        end_time=end,
        event_kind=event_kind,
        price_component=price_component,
    )


def test_v2_execution_stream_preserves_sparse_and_one_sided_fail_closed_behavior(
) -> None:
    snapshot = SimpleNamespace(id=uuid4(), venue_instrument_id=uuid4())
    start = datetime(2026, 1, 5, 12, tzinfo=UTC)
    end = start + timedelta(minutes=1)

    sparse = _stream_v2_execution_coverage(
        _ExecutionSession([_execution_event(start, end, 1)]),
        snapshot,
        start,
        end,
    )
    assert not sparse.has_one_sided_observation
    assert not sparse.has_unacquired_absence
    assert sparse.report.member_minutes == 0
    assert sparse.report.missing[0].components == (
        PriceComponent.BID,
        PriceComponent.ASK,
    )

    unacquired = _stream_v2_execution_coverage(
        _ExecutionSession([]),
        snapshot,
        start,
        end,
    )
    assert unacquired.has_unacquired_absence

    one_sided = _stream_v2_execution_coverage(
        _ExecutionSession(
            [_execution_event(start, end, 0, PriceComponent.BID.value)]
        ),
        snapshot,
        start,
        end,
    )
    assert one_sided.has_one_sided_observation
    assert not one_sided.has_unacquired_absence


def test_v2_experiment_validation_uses_bounded_or_set_based_reads() -> None:
    source = textwrap.dedent(
        inspect.getsource(ExperimentConfigurationService._validate_v2_coverage)
    )
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "all"
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"tuple", "list", "set"}
        for node in ast.walk(tree)
    )
    assert sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
        for node in ast.walk(tree)
    ) >= 1
    assert any(
        isinstance(node, ast.keyword)
        and node.arg == "stream_results"
        for node in ast.walk(tree)
    )

    stream_source = inspect.getsource(_stream_v2_execution_coverage)
    assert ".all(" not in stream_source
    assert ".yield_per(" in stream_source


def test_production_registration_archives_once_and_evaluation_has_no_path_input() -> (
    None
):
    registry = create_production_strategy_registry(Path(__file__).parents[3])
    entry = registry.get(
        "ema_sweep_confirmation_break",
        implementation_key="ema_sweep_confirmation_break.v2",
    )
    assert entry.source_archive.fingerprint
    assert tuple(registry.catalog()) == (entry,)
    assert (
        entry.implementation.definition.implementation_key
        == "ema_sweep_confirmation_break.v2"
    )
    assert entry.implementation.definition.name == "EMA Sweep Confirmation Break"
