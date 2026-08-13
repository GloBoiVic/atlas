import os
import subprocess
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.runtime.main import run


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
