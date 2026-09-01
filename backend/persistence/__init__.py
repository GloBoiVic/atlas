"""PostgreSQL persistence foundation."""

from .lifecycle_locks import (
    DeploymentRuntimeLock,
    acquire_deployment_runtime_lock,
    deployment_advisory_lock_key,
    release_deployment_runtime_lock,
)
from .paper_repository import (
    DeploymentRepository,
    PendingEntryRepository,
    SafetyRepository,
    StrategyStateRepository,
    TradingAccountRepository,
    stable_client_correlation_id,
)

__all__ = [
    "DeploymentRepository",
    "DeploymentRuntimeLock",
    "PendingEntryRepository",
    "SafetyRepository",
    "stable_client_correlation_id",
    "StrategyStateRepository",
    "TradingAccountRepository",
    "acquire_deployment_runtime_lock",
    "deployment_advisory_lock_key",
    "release_deployment_runtime_lock",
]
