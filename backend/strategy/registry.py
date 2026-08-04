"""Trusted registry for explicitly deployed strategy factories."""

from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID

from backend.strategy.base import Strategy

StrategyFactory = Callable[[dict[str, Any]], Strategy]


class StrategyRegistryError(RuntimeError):
    """Base error for fail-closed registry operations."""


class DuplicateStrategyRegistration(StrategyRegistryError):
    """Raised when a strategy version is registered more than once."""


class StrategyNotRegistered(StrategyRegistryError):
    """Raised when a requested version has no trusted registration."""


class StrategyIdentityMismatch(StrategyRegistryError):
    """Raised when persisted identity does not match the deployed registration."""


@dataclass(frozen=True, slots=True)
class RegisteredStrategy:
    strategy_version_id: UUID
    strategy_name: str
    commit_sha: str
    factory: StrategyFactory


class StrategyRegistry:
    """In-memory allow-list of factories supplied by trusted deployment code."""

    def __init__(self) -> None:
        self._registrations: dict[UUID, RegisteredStrategy] = {}

    def register(
        self,
        strategy_version_id: UUID,
        strategy_name: str,
        commit_sha: str,
        factory: StrategyFactory,
    ) -> None:
        """Register one trusted factory, rejecting duplicate identities."""
        if not isinstance(strategy_version_id, UUID):
            raise TypeError("strategy_version_id must be a UUID")
        if not strategy_name or not commit_sha:
            raise ValueError("strategy name and commit SHA must not be empty")
        if strategy_version_id in self._registrations:
            raise DuplicateStrategyRegistration(
                f"strategy version {strategy_version_id} is already registered"
            )
        self._registrations[strategy_version_id] = RegisteredStrategy(
            strategy_version_id,
            strategy_name,
            commit_sha,
            factory,
        )

    def resolve(
        self,
        strategy_version_id: UUID,
        expected_strategy_name: str,
        expected_commit_sha: str,
        config: dict[str, Any],
    ) -> Strategy:
        """Resolve and instantiate only a registered factory with matching identity."""
        registration = self._registrations.get(strategy_version_id)
        if registration is None:
            raise StrategyNotRegistered(f"strategy version {strategy_version_id} is not registered")
        if (
            registration.strategy_name != expected_strategy_name
            or registration.commit_sha != expected_commit_sha
        ):
            raise StrategyIdentityMismatch(
                f"registered identity does not match strategy version {strategy_version_id}"
            )
        strategy = registration.factory(dict(config))
        if not isinstance(strategy, Strategy):
            raise StrategyIdentityMismatch("registered factory did not return a Strategy")
        return strategy
