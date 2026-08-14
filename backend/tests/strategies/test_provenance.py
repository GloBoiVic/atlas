from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from backend.domain.strategy import (
    StrategyEvaluation,
    StrategyParameters,
    StrategyState,
    StrategyVersion,
)
from backend.strategies.contract import StrategyDefinition, StrategyRegistration
from backend.strategies.fingerprint import (
    SourceValidationError,
    archive_source,
    fingerprint_source,
)
from backend.strategies.registry import (
    RegistrationValidationError,
    StrategyRegistry,
    StrategyVersionUnavailableError,
)


def write_sources(
    tmp_path: Path,
    names: tuple[str, ...] = ("backend/a.py", "backend/b.py"),
) -> None:
    for name in names:
        path = tmp_path / Path(*name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {name}\n", encoding="utf-8")


def test_fingerprint_is_order_and_checkout_path_independent(
    tmp_path: Path, tmp_path_factory: Any
) -> None:
    write_sources(tmp_path)
    other = tmp_path_factory.mktemp("checkout")
    write_sources(other)
    first = archive_source(tmp_path, ("backend/b.py", "backend/a.py"))
    second = archive_source(other, ("backend/a.py", "backend/b.py"))
    assert first.fingerprint == second.fingerprint
    assert first.fingerprint == fingerprint_source(
        tmp_path, ("backend/b.py", "backend/a.py")
    )
    assert first.manifest == (("backend/a.py", 15), ("backend/b.py", 15))
    assert first.exact_source_snapshot[0][1] == b"# backend/a.py\n"


@pytest.mark.parametrize(
    "paths",
    [
        ("backend/a.py", "backend/a.py"),
        ("../backend/a.py",),
        ("backend/../a.py",),
        ("/backend/a.py",),
        ("backend\\a.py",),
    ],
)
def test_source_allow_list_rejects_unsafe_paths(
    tmp_path: Path, paths: tuple[str, ...]
) -> None:
    with pytest.raises(SourceValidationError):
        archive_source(tmp_path, paths)


def test_source_rejects_symlink_and_non_utf8(tmp_path: Path) -> None:
    write_sources(tmp_path, ("backend/a.py",))
    (tmp_path / "backend/link.py").symlink_to(tmp_path / "backend/a.py")
    with pytest.raises(SourceValidationError, match="symlink"):
        archive_source(tmp_path, ("backend/link.py",))
    (tmp_path / "backend/bad.py").write_bytes(b"\xff")
    with pytest.raises(SourceValidationError, match="UTF-8"):
        archive_source(tmp_path, ("backend/bad.py",))


class FixtureStrategy:
    definition = StrategyDefinition(
        "fixture", "Fixture", "test", (), implementation_key="fixture"
    )

    def evaluate(
        self,
        context: Any,
        parameters: StrategyParameters,
        state: StrategyState,
    ) -> StrategyEvaluation:
        raise NotImplementedError


def test_registry_aggregates_contract_and_filesystem_errors(tmp_path: Path) -> None:
    definition = StrategyDefinition(
        "fixture",
        "Fixture",
        "test",
        (),
        source_files=("backend/missing.py",),
        implementation_key="fixture",
    )
    registration = StrategyRegistration(definition, object())  # type: ignore[arg-type]
    with pytest.raises(RegistrationValidationError) as raised:
        StrategyRegistry().register(registration, tmp_path)
    assert "registration:" in str(raised.value)
    assert "source_files" in str(raised.value)


def test_registry_matches_fingerprint_and_does_not_need_import_discovery(
    tmp_path: Path,
) -> None:
    write_sources(tmp_path, ("backend/a.py",))
    definition = StrategyDefinition(
        "fixture",
        "Fixture",
        "test",
        (),
        source_files=("backend/a.py",),
        implementation_key="fixture",
    )
    implementation = FixtureStrategy()
    implementation.definition = definition  # type: ignore[misc]
    entry = StrategyRegistry().register(
        StrategyRegistration(definition, implementation), tmp_path
    )
    version = StrategyVersion(
        uuid4(), "fixture", 1, entry.source_archive.fingerprint, "fixture", ()
    )
    loaded = StrategyRegistry((entry,)).implementation_for_version(version)
    assert entry.implementation is loaded
    mismatched = StrategyVersion(uuid4(), "fixture", 1, "0" * 64, "fixture", ())
    with pytest.raises(StrategyVersionUnavailableError, match="fingerprint"):
        StrategyRegistry((entry,)).implementation_for_version(mismatched)
