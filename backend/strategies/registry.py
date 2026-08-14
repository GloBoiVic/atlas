"""Small, explicit local Strategy registration and provenance matching."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from backend.domain.strategy import StrategyVersion

from .contract import (
    Strategy,
    StrategyRegistration,
    validate_registration,
)
from .fingerprint import SourceArchive, SourceValidationError, archive_source


class RegistrationValidationError(ValueError):
    """Registration failed; every reported item is actionable."""

    def __init__(self, errors: tuple[str, ...]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class StrategyVersionUnavailableError(LookupError):
    """The requested persisted version is not represented by local code."""


@dataclass(frozen=True, slots=True)
class LocalStrategy:
    registration: StrategyRegistration
    source_archive: SourceArchive

    @property
    def definition(self):
        return self.registration.definition

    @property
    def implementation(self) -> Strategy:
        return self.registration.implementation


class StrategyRegistry:
    """An in-process registry populated only by explicit caller registration."""

    def __init__(self, entries: Iterable[LocalStrategy] = ()) -> None:
        self._entries: dict[str, LocalStrategy] = {}
        for entry in entries:
            self._add(entry)

    def _add(self, entry: LocalStrategy) -> None:
        key = entry.definition.strategy_key
        if key in self._entries:
            raise RegistrationValidationError(
                (f"strategy_key {key!r}: duplicate registration",)
            )
        self._entries[key] = entry

    def register(self, registration: StrategyRegistration, root: Path) -> LocalStrategy:
        """Validate and snapshot one implementation.

        This is the only filesystem entry point.
        """

        errors: list[str] = []
        try:
            validate_registration(registration)
        except ValueError as error:
            errors.append(f"registration: {error}")
        archive: SourceArchive | None = None
        try:
            archive = archive_source(root, registration.definition.source_files)
        except SourceValidationError as error:
            errors.extend(error.errors)
        if errors or archive is None:
            raise RegistrationValidationError(tuple(sorted(errors)))
        if registration.definition.strategy_key in self._entries:
            raise RegistrationValidationError(
                (
                    f"strategy_key {registration.definition.strategy_key!r}: "
                    "duplicate registration",
                )
            )
        entry = LocalStrategy(registration, archive)
        self._add(entry)
        return entry

    def get(self, strategy_key: str) -> LocalStrategy:
        try:
            return self._entries[strategy_key]
        except KeyError as error:
            raise StrategyVersionUnavailableError(
                f"no locally registered implementation for strategy {strategy_key!r}"
            ) from error

    def implementation_for_version(self, version: StrategyVersion) -> Strategy:
        """Match registration-time provenance; never read the filesystem."""

        entry = self.get(version.strategy_key)
        definition = entry.definition
        if (
            version.source_fingerprint != entry.source_archive.fingerprint
            or version.implementation_key != definition.implementation_key
        ):
            raise StrategyVersionUnavailableError(
                f"StrategyVersion {version.strategy_key!r} fingerprint does not "
                "match local implementation"
            )
        return entry.implementation

    def __len__(self) -> int:
        return len(self._entries)


def register_local_strategy(
    registry: StrategyRegistry,
    registration: StrategyRegistration,
    root: Path,
) -> LocalStrategy:
    """Narrow explicit hook for the single local reference registration."""

    return registry.register(registration, root)
