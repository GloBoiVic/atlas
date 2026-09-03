import os
import subprocess
import sys
import threading
from types import SimpleNamespace
from typing import cast
from unittest.mock import ANY, Mock, patch

from pydantic import SecretStr

from backend.config import Settings
from backend.integrations.oanda import (
    OandaHistoricalBarSource,
    OandaPracticeAccountPropertiesReader,
    OandaPracticeExecutionAccountReader,
)
from backend.paper.durable_execution import PaperDurableExecutionApplication
from backend.paper.reconciliation import PaperReconciliationCoordinator
from backend.runtime.main import create_runtime_orchestrator, run
from backend.runtime.ownership import PaperRuntimeOwner


def settings_stub() -> SimpleNamespace:
    return SimpleNamespace(log_level=SimpleNamespace(value="INFO"))


def test_check_success_disposes_engine() -> None:
    engine = Mock()
    with (
        patch("backend.runtime.main.Settings", return_value=settings_stub()),
        patch("backend.runtime.main.create_database_engine", return_value=engine),
        patch("backend.runtime.main.check_database"),
    ):
        assert run(check_only=True) == 0
    engine.dispose.assert_called_once()


def test_database_failure_returns_one_and_disposes() -> None:
    engine = Mock()
    with (
        patch("backend.runtime.main.Settings", return_value=settings_stub()),
        patch("backend.runtime.main.create_database_engine", return_value=engine),
        patch("backend.runtime.main.check_database", side_effect=RuntimeError),
    ):
        assert run(check_only=True) == 1
    engine.dispose.assert_called_once()


def test_default_waits_then_stops() -> None:
    engine = Mock()
    stop = threading.Event()
    stop.set()
    with (
        patch("backend.runtime.main.Settings", return_value=settings_stub()),
        patch("backend.runtime.main.create_database_engine", return_value=engine),
        patch("backend.runtime.main.check_database"),
    ):
        assert run(stop_event=stop) == 0
    engine.dispose.assert_called_once()


def test_run_invokes_injected_runtime_loop_after_readiness() -> None:
    engine = Mock()
    stop = threading.Event()
    runtime = Mock()
    runtime.run.return_value = 0
    settings = settings_stub()
    factory = Mock(return_value=runtime)

    with (
        patch("backend.runtime.main.Settings", return_value=settings),
        patch("backend.runtime.main.create_database_engine", return_value=engine),
        patch("backend.runtime.main.create_session_factory", return_value=Mock()),
        patch("backend.runtime.main.check_database"),
    ):
        assert run(stop_event=stop, orchestrator_factory=factory) == 0

    factory.assert_called_once_with(
        settings=settings,
        engine=engine,
        session_factory=ANY,
    )
    runtime.run.assert_called_once_with(stop)
    engine.dispose.assert_called_once()


def test_check_does_not_construct_or_run_runtime() -> None:
    engine = Mock()
    factory = Mock()
    with (
        patch("backend.runtime.main.Settings", return_value=settings_stub()),
        patch("backend.runtime.main.create_database_engine", return_value=engine),
        patch("backend.runtime.main.check_database"),
    ):
        assert run(check_only=True, orchestrator_factory=factory) == 0

    factory.assert_not_called()
    engine.dispose.assert_called_once()


class _RuntimeSession:
    def __enter__(self) -> "_RuntimeSession":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def begin(self) -> "_RuntimeSession":
        return self


class _IdleRuntimeRepository:
    def __init__(self) -> None:
        self.activation_lookups = 0

    def get_active_activation(
        self, _session: _RuntimeSession, *, for_update: bool = False
    ) -> None:
        del for_update
        self.activation_lookups += 1
        return None


class _IdleRuntimeOwner:
    acquired = True
    owner_id = "owner"
    owner_generation = 1

    def try_acquire(self) -> object:
        return object()

    def close(self) -> None:
        return None


class _NoProviderAccountReader:
    def __init__(self) -> None:
        self.reads = 0

    def read(self) -> object:
        self.reads += 1
        raise AssertionError("an idle runtime must not read OANDA")


class _NoProviderSource:
    def fetch_native_m15(self, _start: object, _end: object) -> object:
        raise AssertionError("an idle runtime must not read OANDA")


class _IdleStopEvent:
    def __init__(self) -> None:
        self.waited: list[float] = []
        self._set = False

    def is_set(self) -> bool:
        return self._set

    def wait(self, timeout: float) -> None:
        self.waited.append(timeout)
        self._set = True


def test_executable_runs_idle_orchestrator_without_provider_calls() -> None:
    engine = Mock()
    stop = _IdleStopEvent()
    account_reader = _NoProviderAccountReader()
    source = _NoProviderSource()
    repository = _IdleRuntimeRepository()
    from backend.runtime.orchestration import PaperRuntimeOrchestrator

    runtime = PaperRuntimeOrchestrator(
        owner=_IdleRuntimeOwner(),  # type: ignore[arg-type]
        session_factory=_RuntimeSession,  # type: ignore[arg-type]
        strategy_registry=object(),  # type: ignore[arg-type]
        analytical_source=source,  # type: ignore[arg-type]
        account_reader=account_reader,
        capability_reader=account_reader,  # type: ignore[arg-type]
        runtime_repository=repository,  # type: ignore[arg-type]
    )
    factory = Mock(return_value=runtime)

    with (
        patch("backend.runtime.main.Settings", return_value=settings_stub()),
        patch("backend.runtime.main.create_database_engine", return_value=engine),
        patch("backend.runtime.main.create_session_factory", return_value=Mock()),
        patch("backend.runtime.main.check_database"),
    ):
        assert run(stop_event=stop, orchestrator_factory=factory) == 0

    assert stop.waited == [15.0]
    assert repository.activation_lookups == 2
    assert account_reader.reads == 0
    engine.dispose.assert_called_once()


def test_runtime_construction_wires_supported_oanda_and_p05_seams() -> None:
    settings = cast(
        Settings,
        SimpleNamespace(
            oanda_api_token=SecretStr("test-token"),
            oanda_account_id="001-002-003-004",
            oanda_connect_timeout_seconds=5,
            oanda_read_timeout_seconds=20,
        ),
    )
    engine = Mock()
    session_factory = Mock()
    registry = Mock()
    constructed = object()

    with patch(
        "backend.runtime.main.PaperRuntimeOrchestrator",
        return_value=constructed,
    ) as orchestrator:
        result = create_runtime_orchestrator(
            settings,
            engine,
            session_factory,
            registry=registry,  # type: ignore[arg-type]
        )

    assert result is constructed
    kwargs = orchestrator.call_args.kwargs
    assert kwargs["strategy_registry"] is registry
    assert isinstance(kwargs["owner"], PaperRuntimeOwner)
    assert isinstance(kwargs["analytical_source"], OandaHistoricalBarSource)
    assert isinstance(kwargs["account_reader"], OandaPracticeExecutionAccountReader)
    assert isinstance(kwargs["capability_reader"], OandaPracticeAccountPropertiesReader)
    assert isinstance(kwargs["durable_execution"], PaperDurableExecutionApplication)
    assert (
        kwargs["durable_execution"]._application._account_properties_reader
        is kwargs["capability_reader"]
    )
    assert isinstance(kwargs["reconciliation"], PaperReconciliationCoordinator)


def test_invalid_configuration_returns_two_without_leaking_secret() -> None:
    environment = dict(os.environ)
    environment["ATLAS_DATABASE_URL"] = "postgresql+psycopg://user:SuperSecretPW@"
    result = subprocess.run(
        [sys.executable, "-c", "from backend.runtime.main import main; main()"],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "SuperSecretPW" not in result.stdout + result.stderr
    assert "postgresql+psycopg://" not in result.stdout + result.stderr
