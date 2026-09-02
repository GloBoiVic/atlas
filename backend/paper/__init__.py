"""Read-only PAPER application seams."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .durable_execution import (
        PaperDurableExecutionApplication,
        PaperDurableExecutionPersistenceError,
        execute_durable_paper_execution,
    )
    from .reconciliation import (
        MAX_ENTRY_RECONCILIATION_TRANSACTIONS,
        MAX_RECONCILIATION_READS,
        PaperReconciliationContext,
        PaperReconciliationCoordinator,
        PaperReconciliationError,
        PaperReconciliationProvider,
        PaperReconciliationRead,
        PaperReconciliationReadState,
        PaperReconciliationResult,
        PaperReconciliationTransaction,
    )

from .current_analytical_frontier import (
    AnalyticalFrontierDataError,
    AnalyticalFrontierError,
    CurrentAnalyticalFrontier,
    NoCurrentAnalyticalFrontierError,
    load_current_analytical_frontier,
)
from .execution import (
    BrokerFillFacts,
    BrokerProtectionOrder,
    BrokerRejection,
    BrokerUncertainty,
    ExecutionAccountIdentity,
    ExecutionCorrelation,
    ExecutionObservationProvenance,
    PaperExecutionContractError,
    PaperExecutionError,
    PaperExecutionInstruction,
    PaperExecutionOutcome,
    PaperExecutionRefusal,
    PaperExecutionRefusalCode,
    PaperExecutionResult,
    ProtectionConfirmation,
    ProtectionLegStatus,
    TransactionProvenance,
    correlation_for_attempt,
)
from .execution_application import (
    AfterTakeProfitMutation,
    BeforeTakeProfitMutation,
    PaperEntryMutation,
    PaperExecutionApplication,
    PaperExecutionMutationBarrierError,
    PaperExecutionPreparation,
    PaperExecutionReader,
    PaperPricingReader,
    PaperProtectionCompletion,
    PricingReaderFactory,
    execute_paper_execution,
)
from .persistence_contracts import (
    MAX_CANONICAL_SNAPSHOT_BYTES,
    MAX_NORMALIZED_FACTS_BYTES,
    PAPER_BROKER_FACTS_SCHEMA_V1,
    PAPER_RISK_AUTHORITY_SCHEMA_V1,
    PAPER_STRATEGY_RECEIPT_SCHEMA_V1,
    PaperBrokerObservation,
    PaperExecutionAttempt,
    PaperMutationClaim,
    PaperMutationPhase,
    PaperObservationObjectKind,
    PaperObservationReadKind,
    PaperPersistenceContractError,
    PaperReconciliationFinding,
    PaperReconciliationFindingCode,
    PaperReconciliationRun,
    PaperReconciliationRunStatus,
    PaperRiskAuthoritySnapshot,
    PaperStrategyEvaluationReceipt,
    ReconciliationStatus,
    canonical_json_bytes,
    validate_execution_outcome_transition,
)
from .risk_evaluation import (
    PaperCandidateRiskEvaluation,
    PaperObservationProvenance,
    PaperPricingEvidence,
    PaperRiskEvaluation,
    PaperRiskEvaluationError,
    PaperRiskOutcome,
    evaluate_paper_risk,
)
from .strategy_evaluation import (
    PaperStrategyEvaluationError,
    evaluate_current_paper_strategy,
    evaluate_current_paper_strategy_receipt,
)

__all__ = [
    "AnalyticalFrontierDataError",
    "AnalyticalFrontierError",
    "CurrentAnalyticalFrontier",
    "NoCurrentAnalyticalFrontierError",
    "PaperEntryMutation",
    "PaperExecutionApplication",
    "PaperExecutionMutationBarrierError",
    "PaperExecutionPreparation",
    "AfterTakeProfitMutation",
    "BeforeTakeProfitMutation",
    "PaperDurableExecutionApplication",
    "PaperDurableExecutionPersistenceError",
    "PaperExecutionReader",
    "PaperPricingReader",
    "PaperProtectionCompletion",
    "PricingReaderFactory",
    "BrokerFillFacts",
    "BrokerProtectionOrder",
    "BrokerRejection",
    "BrokerUncertainty",
    "ExecutionAccountIdentity",
    "ExecutionCorrelation",
    "ExecutionObservationProvenance",
    "PaperExecutionContractError",
    "PaperExecutionError",
    "PaperExecutionInstruction",
    "PaperExecutionOutcome",
    "PaperExecutionRefusal",
    "PaperExecutionRefusalCode",
    "PaperExecutionResult",
    "PaperCandidateRiskEvaluation",
    "PaperObservationProvenance",
    "PaperPricingEvidence",
    "PaperRiskEvaluation",
    "PaperRiskEvaluationError",
    "PaperRiskOutcome",
    "PaperStrategyEvaluationError",
    "ProtectionConfirmation",
    "ProtectionLegStatus",
    "TransactionProvenance",
    "correlation_for_attempt",
    "evaluate_current_paper_strategy",
    "evaluate_current_paper_strategy_receipt",
    "execute_paper_execution",
    "execute_durable_paper_execution",
    "MAX_ENTRY_RECONCILIATION_TRANSACTIONS",
    "MAX_RECONCILIATION_READS",
    "PaperReconciliationContext",
    "PaperReconciliationCoordinator",
    "PaperReconciliationError",
    "PaperReconciliationProvider",
    "PaperReconciliationRead",
    "PaperReconciliationReadState",
    "PaperReconciliationResult",
    "PaperReconciliationTransaction",
    "evaluate_paper_risk",
    "load_current_analytical_frontier",
    "MAX_CANONICAL_SNAPSHOT_BYTES",
    "MAX_NORMALIZED_FACTS_BYTES",
    "PAPER_BROKER_FACTS_SCHEMA_V1",
    "PAPER_RISK_AUTHORITY_SCHEMA_V1",
    "PAPER_STRATEGY_RECEIPT_SCHEMA_V1",
    "PaperBrokerObservation",
    "PaperExecutionAttempt",
    "PaperMutationClaim",
    "PaperMutationPhase",
    "PaperObservationObjectKind",
    "PaperObservationReadKind",
    "PaperPersistenceContractError",
    "PaperReconciliationFinding",
    "PaperReconciliationFindingCode",
    "PaperReconciliationRun",
    "PaperReconciliationRunStatus",
    "PaperRiskAuthoritySnapshot",
    "PaperStrategyEvaluationReceipt",
    "ReconciliationStatus",
    "canonical_json_bytes",
    "validate_execution_outcome_transition",
]


def __getattr__(name: str) -> object:
    """Load persistence-backed execution lazily to keep package imports acyclic."""
    if name == "PaperDurableExecutionApplication":
        from .durable_execution import PaperDurableExecutionApplication

        return PaperDurableExecutionApplication
    if name == "PaperDurableExecutionPersistenceError":
        from .durable_execution import PaperDurableExecutionPersistenceError

        return PaperDurableExecutionPersistenceError
    if name == "execute_durable_paper_execution":
        from .durable_execution import execute_durable_paper_execution

        return execute_durable_paper_execution
    if name in {
        "MAX_ENTRY_RECONCILIATION_TRANSACTIONS",
        "MAX_RECONCILIATION_READS",
        "PaperReconciliationContext",
        "PaperReconciliationCoordinator",
        "PaperReconciliationError",
        "PaperReconciliationProvider",
        "PaperReconciliationRead",
        "PaperReconciliationReadState",
        "PaperReconciliationResult",
        "PaperReconciliationTransaction",
    }:
        from . import reconciliation

        return getattr(reconciliation, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
