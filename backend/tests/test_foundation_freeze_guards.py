"""Static guards for the frozen Strategy extensibility boundary.

These tests deliberately inspect only the shared seams.  The candidate is
allowed to mention its own identity and parameters in its Strategy module, but
the orchestration, financial, market-data, and result layers must remain
identity-neutral.
"""

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]

SHARED_SEAMS = (
    "backend/experiments/configuration.py",
    "backend/experiments/runner.py",
    "backend/risk/service.py",
    "backend/execution/simulated.py",
    "backend/market_data/ingestion.py",
    "backend/persistence/market_data_repository.py",
    "backend/experiments/results.py",
)

CANDIDATE_IDENTIFIERS = {
    "candle_confirmation_break",
    "candleconfirmationbreak",
    "candleconfirmationbreakstrategy",
    "candle_confirmation_break_strategy",
}

EMA_PARAMETER_NAMES = {
    "ema_period",
    "atr_period",
    "stop_buffer",
    "expiry_window",
}


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text()


def _tree(relative_path: str) -> ast.Module:
    return ast.parse(_source(relative_path), filename=relative_path)


def _node_identifiers(tree: ast.AST) -> set[str]:
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr.lower())
    return identifiers


def _string_constants(tree: ast.AST) -> tuple[str, ...]:
    return tuple(
        node.value.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def test_shared_seams_have_no_candidate_identity_branch() -> None:
    for relative_path in SHARED_SEAMS:
        tree = _tree(relative_path)
        identifiers = _node_identifiers(tree)
        strings = _string_constants(tree)
        assert not CANDIDATE_IDENTIFIERS & identifiers, relative_path
        assert not any(
            candidate in value
            for value in strings
            for candidate in CANDIDATE_IDENTIFIERS
        ), relative_path


def test_configuration_and_runner_do_not_construct_ema_parameters() -> None:
    for relative_path in (
        "backend/experiments/configuration.py",
        "backend/experiments/runner.py",
    ):
        tree = _tree(relative_path)
        identifiers = _node_identifiers(tree)
        strings = _string_constants(tree)
        assert not EMA_PARAMETER_NAMES & identifiers, relative_path
        assert not any(
            value == "strategyparameters" or value in EMA_PARAMETER_NAMES
            for value in strings
        ), relative_path
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "StrategyParameters"
            for node in ast.walk(tree)
        ), relative_path


def test_risk_and_execution_do_not_own_pip_conversion() -> None:
    for relative_path in (
        "backend/risk/service.py",
        "backend/execution/simulated.py",
    ):
        tree = _tree(relative_path)
        assert not any("pip" in identifier for identifier in _node_identifiers(tree)), (
            relative_path
        )
        assert not any("pip" in value for value in _string_constants(tree)), (
            relative_path
        )


def test_freeze_adds_no_migration_or_durable_checkpoint_artifact() -> None:
    changed = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "50c5e18b27d2d652c807f4ca3068ca66cd664687",
            "--",
            "backend/persistence/migrations",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert changed == []

    migration_status = subprocess.run(
        [
            "git",
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            "backend/persistence/migrations",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert migration_status == []

    checkpoint_paths = tuple(
        path
        for area in (ROOT / "backend", ROOT / "frontend")
        for path in area.rglob("*")
        if "checkpoint" in path.name.lower()
    )
    assert checkpoint_paths == ()

    for path in (ROOT / "backend").rglob("*.py"):
        if "tests" not in path.parts and "migrations" not in path.parts:
            assert "checkpoint" not in path.read_text().lower(), path

    runner_tree = _tree("backend/experiments/runner.py")
    durable_state_calls = {
        node.func.attr.lower()
        for node in ast.walk(runner_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.lower()
        in {
            "checkpoint",
            "create_checkpoint",
            "save_checkpoint",
            "persist_state",
            "save_state",
        }
    }
    assert durable_state_calls == set()


def test_legacy_ema_sweep_engulfing_candidate_remains_inactive() -> None:
    production = _source("backend/strategies/production.py")
    assert "ema_sweep_engulfing" not in production

    from backend.strategies.production import create_production_strategy_registry

    registry = create_production_strategy_registry(ROOT)
    assert all(
        entry.definition.strategy_key != "ema_sweep_engulfing"
        for entry in registry.catalog()
    )
