"""Atlas runtime process and durable runtime contracts."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .activation import (
        PaperActivationRequest,
        PaperRuntimeActivationResult,
        PaperRuntimeActivationService,
        PaperRuntimeCapability,
        PaperRuntimeConfigurationError,
        PaperRuntimeControlConflict,
        PaperRuntimeControlService,
        PaperRuntimeReconcileResult,
        PaperRuntimeReconciliationService,
        PaperRuntimeService,
        PaperRuntimeServiceError,
        PaperRuntimeStatus,
        PaperStopRequest,
    )
    from .cycles import (
        PaperRuntimeAccountObservation,
        PaperRuntimeCycleAuthority,
        PaperRuntimeFrontierAlreadyConsumed,
        PaperRuntimeFrontierDuplicate,
        PaperRuntimeFrontierGap,
        PaperRuntimeStateAuthorityError,
        PaperRuntimeUnattributedExposure,
        PaperRuntimeUnsupportedStrategyAction,
    )
    from .orchestration import (
        PaperRuntime,
        PaperRuntimeAccountReader,
        PaperRuntimeCapabilityReader,
        PaperRuntimeLoop,
        PaperRuntimeOrchestrator,
        PaperRuntimeReconciliation,
        PaperRuntimeRunner,
        PaperRuntimeStartupResult,
        PaperRuntimeTickOutcome,
        PaperRuntimeTickResult,
    )
    from .ownership import (
        PAPER_RUNTIME_ADVISORY_LOCK_KEY,
        PaperRuntimeOwner,
        PaperRuntimeOwnerConfigurationError,
        PaperRuntimeOwnerError,
        PaperRuntimeOwnerLost,
        PaperRuntimeOwnerNotAcquired,
        PaperRuntimeOwnerUnavailable,
    )

from .persistence_contracts import (
    MAX_RUNTIME_JSON_BYTES,
    PAPER_RUNTIME_APPROVAL_CODE,
    PAPER_RUNTIME_APPROVAL_KIND,
    PAPER_RUNTIME_BASE_CURRENCY,
    PAPER_RUNTIME_ENVIRONMENT,
    PAPER_RUNTIME_INSTRUMENT,
    PAPER_RUNTIME_POLICY_V1,
    PAPER_RUNTIME_POLL_INTERVAL_SECONDS,
    PAPER_RUNTIME_PROVIDER,
    PAPER_RUNTIME_SLOT,
    PaperRuntimeActivation,
    PaperRuntimeCycle,
    PaperRuntimeCycleStatus,
    PaperRuntimeLifecycleState,
    PaperRuntimeOperationalPhase,
    PaperRuntimeOwnership,
    PaperRuntimeOwnershipPhase,
    PaperRuntimePersistenceError,
    PaperRuntimeStateOrigin,
    canonical_decimal_text,
    canonical_json_bytes,
    is_non_terminal_lifecycle,
    is_terminal_cycle_status,
    runtime_evaluation_key,
    runtime_parameter_fingerprint,
    validate_runtime_json_object,
)

__all__ = [
    "PaperActivationRequest",
    "PaperRuntimeActivationResult",
    "PaperRuntimeActivationService",
    "PaperRuntimeCapability",
    "PaperRuntimeConfigurationError",
    "PaperRuntimeControlConflict",
    "PaperRuntimeControlService",
    "PaperRuntimeReconcileResult",
    "PaperRuntimeReconciliationService",
    "PaperRuntimeService",
    "PaperRuntimeServiceError",
    "PaperRuntimeStatus",
    "PaperStopRequest",
    "PAPER_RUNTIME_ADVISORY_LOCK_KEY",
    "PaperRuntimeOwner",
    "PaperRuntimeOwnerConfigurationError",
    "PaperRuntimeOwnerError",
    "PaperRuntimeOwnerLost",
    "PaperRuntimeOwnerNotAcquired",
    "PaperRuntimeOwnerUnavailable",
    "PaperRuntime",
    "PaperRuntimeAccountReader",
    "PaperRuntimeCapabilityReader",
    "PaperRuntimeLoop",
    "PaperRuntimeOrchestrator",
    "PaperRuntimeReconciliation",
    "PaperRuntimeRunner",
    "PaperRuntimeStartupResult",
    "PaperRuntimeTickOutcome",
    "PaperRuntimeTickResult",
    "PaperRuntimeAccountObservation",
    "PaperRuntimeCycleAuthority",
    "PaperRuntimeFrontierAlreadyConsumed",
    "PaperRuntimeFrontierDuplicate",
    "PaperRuntimeFrontierGap",
    "PaperRuntimeStateAuthorityError",
    "PaperRuntimeUnsupportedStrategyAction",
    "PaperRuntimeUnattributedExposure",
    "MAX_RUNTIME_JSON_BYTES",
    "PAPER_RUNTIME_APPROVAL_CODE",
    "PAPER_RUNTIME_APPROVAL_KIND",
    "PAPER_RUNTIME_BASE_CURRENCY",
    "PAPER_RUNTIME_ENVIRONMENT",
    "PAPER_RUNTIME_INSTRUMENT",
    "PAPER_RUNTIME_POLL_INTERVAL_SECONDS",
    "PAPER_RUNTIME_POLICY_V1",
    "PAPER_RUNTIME_PROVIDER",
    "PAPER_RUNTIME_SLOT",
    "PaperRuntimeActivation",
    "PaperRuntimeCycle",
    "PaperRuntimeCycleStatus",
    "PaperRuntimeLifecycleState",
    "PaperRuntimeOperationalPhase",
    "PaperRuntimeOwnership",
    "PaperRuntimeOwnershipPhase",
    "PaperRuntimePersistenceError",
    "PaperRuntimeStateOrigin",
    "canonical_decimal_text",
    "canonical_json_bytes",
    "is_non_terminal_lifecycle",
    "is_terminal_cycle_status",
    "runtime_evaluation_key",
    "runtime_parameter_fingerprint",
    "validate_runtime_json_object",
]


_ACTIVATION_EXPORTS = frozenset(
    {
        "PaperActivationRequest",
        "PaperRuntimeActivationResult",
        "PaperRuntimeActivationService",
        "PaperRuntimeCapability",
        "PaperRuntimeConfigurationError",
        "PaperRuntimeControlConflict",
        "PaperRuntimeControlService",
        "PaperRuntimeReconcileResult",
        "PaperRuntimeReconciliationService",
        "PaperRuntimeService",
        "PaperRuntimeServiceError",
        "PaperRuntimeStatus",
        "PaperStopRequest",
    }
)

_OWNERSHIP_EXPORTS = frozenset(
    {
        "PAPER_RUNTIME_ADVISORY_LOCK_KEY",
        "PaperRuntimeOwner",
        "PaperRuntimeOwnerConfigurationError",
        "PaperRuntimeOwnerError",
        "PaperRuntimeOwnerLost",
        "PaperRuntimeOwnerNotAcquired",
        "PaperRuntimeOwnerUnavailable",
    }
)

_CYCLE_EXPORTS = frozenset(
    {
        "PaperRuntimeAccountObservation",
        "PaperRuntimeCycleAuthority",
        "PaperRuntimeFrontierAlreadyConsumed",
        "PaperRuntimeFrontierDuplicate",
        "PaperRuntimeFrontierGap",
        "PaperRuntimeStateAuthorityError",
        "PaperRuntimeUnsupportedStrategyAction",
        "PaperRuntimeUnattributedExposure",
    }
)

_ORCHESTRATION_EXPORTS = frozenset(
    {
        "PaperRuntime",
        "PaperRuntimeAccountReader",
        "PaperRuntimeCapabilityReader",
        "PaperRuntimeLoop",
        "PaperRuntimeOrchestrator",
        "PaperRuntimeReconciliation",
        "PaperRuntimeRunner",
        "PaperRuntimeStartupResult",
        "PaperRuntimeTickOutcome",
        "PaperRuntimeTickResult",
    }
)


def __getattr__(name: str) -> object:
    """Load application services lazily to keep persistence imports acyclic."""
    if name in _ACTIVATION_EXPORTS:
        from . import activation

        return getattr(activation, name)
    if name in _OWNERSHIP_EXPORTS:
        from . import ownership

        return getattr(ownership, name)
    if name in _CYCLE_EXPORTS:
        from . import cycles

        return getattr(cycles, name)
    if name in _ORCHESTRATION_EXPORTS:
        from . import orchestration

        return getattr(orchestration, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
