"""Small, explicit local Strategy registration and provenance matching."""

from collections.abc import Iterable, Iterator
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
        self._entries: dict[tuple[str, str, str], LocalStrategy] = {}
        for entry in entries:
            self._add(entry)

    def _add(self, entry: LocalStrategy) -> None:
        definition = entry.definition
        key = (
            definition.strategy_key,
            definition.implementation_key,
            entry.source_archive.fingerprint,
        )
        if any(
            existing.definition.strategy_key == definition.strategy_key
            and existing.definition.implementation_key == definition.implementation_key
            for existing in self._entries.values()
        ):
            raise RegistrationValidationError(
                (
                    f"strategy_key {definition.strategy_key!r}: duplicate "
                    f"implementation_key {definition.implementation_key!r}",
                )
            )
        if key in self._entries:
            raise RegistrationValidationError(
                (f"registration {key!r}: duplicate provenance",)
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
        entry = LocalStrategy(registration, archive)
        self._add(entry)
        return entry

    def get(
        self,
        strategy_key: str,
        *,
        implementation_key: str | None = None,
        source_fingerprint: str | None = None,
    ) -> LocalStrategy:
        matches = tuple(
            entry
            for entry in self._entries.values()
            if entry.definition.strategy_key == strategy_key
            and (
                implementation_key is None
                or entry.definition.implementation_key == implementation_key
            )
            and (
                source_fingerprint is None
                or entry.source_archive.fingerprint == source_fingerprint
            )
        )
        if len(matches) == 1:
            return matches[0]
        detail = (
            "ambiguous local implementations"
            if matches
            else "no locally registered implementation"
        )
        raise StrategyVersionUnavailableError(
            f"{detail} for strategy {strategy_key!r}"
        )

    def catalog(self) -> Iterator[LocalStrategy]:
        """Return explicit registrations in stable catalog order."""
        return iter(
            sorted(
                self._entries.values(),
                key=lambda entry: (
                    entry.definition.strategy_key,
                    entry.definition.implementation_key,
                    entry.source_archive.fingerprint,
                ),
            )
        )

    def implementation_for_version(self, version: StrategyVersion) -> Strategy:
        """Match registration-time provenance; never read the filesystem."""

        try:
            entry = self.get(
                version.strategy_key,
                implementation_key=version.implementation_key,
                source_fingerprint=version.source_fingerprint,
            )
        except StrategyVersionUnavailableError as error:
            raise StrategyVersionUnavailableError(
                f"StrategyVersion {version.strategy_key!r} fingerprint or "
                "implementation key does not match local implementation"
            ) from error
        return entry.implementation

    def __len__(self) -> int:
        return len(self._entries)


def register_local_strategy(
    registry: StrategyRegistry,
    registration: StrategyRegistration,
    root: Path,
) -> LocalStrategy:
    """Narrow explicit hook for an explicit local registration."""

    return registry.register(registration, root)
