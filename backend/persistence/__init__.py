"""PostgreSQL persistence foundation."""

from .paper_execution_repository import (
    DuplicateMutationClaim,
    FillConflict,
    InvalidPaperTransition,
    PaperAttemptNotFound,
    PaperExecutionRepository,
    PaperIdentityConflict,
    PaperRepositoryError,
    StaleReconciliationError,
)
from .runtime_repository import (
    InvalidPaperRuntimeTransition,
    PaperRuntimeActivationAlreadyPresent,
    PaperRuntimeActivationNotFound,
    PaperRuntimeCycleConflict,
    PaperRuntimeCycleNotFound,
    PaperRuntimeIdentityConflict,
    PaperRuntimeOwnerLost,
    PaperRuntimeOwnershipNotFound,
    PaperRuntimeRepository,
    PaperRuntimeRepositoryError,
)

__all__ = [
    "DuplicateMutationClaim",
    "FillConflict",
    "InvalidPaperTransition",
    "PaperAttemptNotFound",
    "PaperExecutionRepository",
    "PaperIdentityConflict",
    "PaperRepositoryError",
    "StaleReconciliationError",
    "InvalidPaperRuntimeTransition",
    "PaperRuntimeActivationAlreadyPresent",
    "PaperRuntimeActivationNotFound",
    "PaperRuntimeCycleConflict",
    "PaperRuntimeCycleNotFound",
    "PaperRuntimeIdentityConflict",
    "PaperRuntimeOwnershipNotFound",
    "PaperRuntimeOwnerLost",
    "PaperRuntimeRepository",
    "PaperRuntimeRepositoryError",
]
