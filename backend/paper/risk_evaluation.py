"""Pure, read-only composition of current PAPER Risk observations.

This module deliberately stops at an observation-time Risk decision.  It does
not read configuration, call OANDA, persist state, or create an Order.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from backend.domain import (
    Action,
    Direction,
    EntryPolicy,
    Instrument,
    Provider,
    StrategyDecision,
)
from backend.integrations.oanda import (
    OandaExposureProjectionError,
    OandaPracticeAccountIdentity,
    OandaPracticeAccountSummarySnapshot,
    OandaPracticeEurUsdPricingObservation,
    OandaPracticeExecutablePriceCandidate,
    OandaPracticeExecutablePricingProjection,
    OandaPracticeOpenPositionInventory,
    OandaPracticeOpenTradeInventory,
    OandaPracticePriceBucket,
    OandaPricingBucketEvidence,
    project_oanda_practice_account_state,
    project_oanda_practice_eur_usd_exposure_state,
    project_oanda_practice_executable_pricing,
)
from backend.risk import (
    ExecutablePrice,
    RiskConfig,
    RiskDecision,
    RiskRejection,
    RiskService,
    TradeIntent,
)


class PaperRiskEvaluationError(ValueError):
    """The PAPER Risk composition received an invalid contract value."""


class PaperRiskOutcome(StrEnum):
    """The finite outcomes of the read-only PAPER Risk composition."""

    APPROVED = "APPROVED"
    NO_ACTION = "NO_ACTION"
    DEFERRED_ENTRY_POLICY = "DEFERRED_ENTRY_POLICY"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    OBSERVATION_MISMATCH = "OBSERVATION_MISMATCH"
    ENTRY_STATE_BLOCKED = "ENTRY_STATE_BLOCKED"
    PRICING_REJECTED = "PRICING_REJECTED"
    PRE_FLIGHT_REJECTED = "PRE_FLIGHT_REJECTED"
    PRE_SUBMISSION_REJECTED = "PRE_SUBMISSION_REJECTED"


@dataclass(frozen=True, slots=True)
class PaperObservationProvenance:
    """Identity and transaction labels retained from a coherent observation set."""

    provider: Provider
    environment: str
    provider_account_id: str
    base_currency: str
    price_time: datetime
    summary_last_transaction_id: str
    trades_last_transaction_id: str
    positions_last_transaction_id: str

    def __post_init__(self) -> None:
        if type(self.provider) is not Provider:
            raise PaperRiskEvaluationError("PAPER provenance has an invalid provider")
        if type(self.environment) is not str or not self.environment:
            raise PaperRiskEvaluationError(
                "PAPER provenance has an invalid environment"
            )
        for value, name in (
            (self.provider_account_id, "provider_account_id"),
            (self.base_currency, "base_currency"),
            (self.summary_last_transaction_id, "summary_last_transaction_id"),
            (self.trades_last_transaction_id, "trades_last_transaction_id"),
            (self.positions_last_transaction_id, "positions_last_transaction_id"),
        ):
            if type(value) is not str or not value:
                raise PaperRiskEvaluationError(f"PAPER provenance has invalid {name}")
        if type(self.price_time) is not datetime:
            raise PaperRiskEvaluationError("PAPER provenance has an invalid price_time")
        if self.price_time.tzinfo is None or self.price_time.utcoffset() is None:
            raise PaperRiskEvaluationError(
                "PAPER provenance price_time must be timezone-aware"
            )
        object.__setattr__(self, "price_time", self.price_time.astimezone(UTC))

    @property
    def pricing_price_time(self) -> datetime:
        """Compatibility spelling that makes the pricing source explicit."""
        return self.price_time

    @property
    def transaction_ids(self) -> tuple[str, str, str]:
        """Return transaction labels in summary, Trades, Positions order."""
        return (
            self.summary_last_transaction_id,
            self.trades_last_transaction_id,
            self.positions_last_transaction_id,
        )


@dataclass(frozen=True, slots=True)
class PaperCandidateRiskEvaluation:
    """The Risk result for one finite provider-pricing candidate."""

    candidate: OandaPracticeExecutablePriceCandidate
    decision: RiskDecision

    def __post_init__(self) -> None:
        if type(self.candidate) is not OandaPracticeExecutablePriceCandidate:
            raise PaperRiskEvaluationError(
                "PAPER candidate evidence has an invalid candidate"
            )
        if type(self.decision) is not RiskDecision:
            raise PaperRiskEvaluationError(
                "PAPER candidate evidence has an invalid decision"
            )

    @property
    def price(self) -> Decimal:
        return self.candidate.price

    @property
    def available_quantity(self) -> Decimal:
        return self.candidate.available_quantity


@dataclass(frozen=True, slots=True)
class PaperPricingEvidence:
    """The complete required-side pricing and per-candidate Risk evidence."""

    projection: OandaPracticeExecutablePricingProjection
    candidate_evaluations: tuple[PaperCandidateRiskEvaluation, ...]
    selected_candidate: OandaPracticeExecutablePriceCandidate | None = None

    def __post_init__(self) -> None:
        if type(self.projection) is not OandaPracticeExecutablePricingProjection:
            raise PaperRiskEvaluationError(
                "PAPER pricing evidence has an invalid projection"
            )
        if type(self.candidate_evaluations) is not tuple or any(
            type(item) is not PaperCandidateRiskEvaluation
            for item in self.candidate_evaluations
        ):
            raise PaperRiskEvaluationError(
                "PAPER pricing evidence has invalid candidate evaluations"
            )
        expected_candidates = self.projection.candidates
        actual_candidates = tuple(item.candidate for item in self.candidate_evaluations)
        if actual_candidates != expected_candidates:
            raise PaperRiskEvaluationError(
                "PAPER pricing evidence does not cover every candidate"
            )
        if self.selected_candidate is not None and self.selected_candidate not in (
            expected_candidates
        ):
            raise PaperRiskEvaluationError(
                "PAPER pricing evidence selected an unknown candidate"
            )

    @property
    def observation(self) -> OandaPracticeEurUsdPricingObservation:
        return self.projection.observation

    @property
    def direction(self) -> Direction:
        return self.projection.direction

    @property
    def required_side(self) -> str:
        return self.projection.required_side

    @property
    def source_buckets(self) -> tuple[OandaPracticePriceBucket, ...]:
        """Return every normalized required-side source bucket."""
        return self.projection.source_buckets

    @property
    def evidence(self) -> tuple[OandaPricingBucketEvidence, ...]:
        """Return each source bucket with its candidate disposition."""
        return self.projection.evidence

    @property
    def candidates(self) -> tuple[OandaPracticeExecutablePriceCandidate, ...]:
        return self.projection.candidates

    @property
    def candidate_results(self) -> tuple[PaperCandidateRiskEvaluation, ...]:
        return self.candidate_evaluations

    @property
    def selected_candidate_evaluation(self) -> PaperCandidateRiskEvaluation | None:
        if self.selected_candidate is None:
            return None
        return next(
            item
            for item in self.candidate_evaluations
            if item.candidate == self.selected_candidate
        )


@dataclass(frozen=True, slots=True)
class PaperRiskEvaluation:
    """Immutable result of one read-only PAPER Risk composition."""

    outcome: PaperRiskOutcome
    strategy_decision: StrategyDecision
    trade_intent: TradeIntent | None
    pre_flight: RiskDecision | None
    pre_submission: RiskDecision | None
    provenance: PaperObservationProvenance | None
    pricing_evidence: PaperPricingEvidence | None

    def __post_init__(self) -> None:
        if type(self.outcome) is not PaperRiskOutcome:
            raise PaperRiskEvaluationError("PAPER result has an invalid outcome")
        if type(self.strategy_decision) is not StrategyDecision:
            raise PaperRiskEvaluationError(
                "PAPER result has an invalid Strategy decision"
            )
        for value, expected_type, name in (
            (self.trade_intent, TradeIntent, "trade_intent"),
            (self.pre_flight, RiskDecision, "pre_flight"),
            (self.pre_submission, RiskDecision, "pre_submission"),
            (self.provenance, PaperObservationProvenance, "provenance"),
            (self.pricing_evidence, PaperPricingEvidence, "pricing_evidence"),
        ):
            if value is not None and type(value) is not expected_type:
                raise PaperRiskEvaluationError(f"PAPER result has an invalid {name}")


def evaluate_paper_risk(
    strategy_decision: StrategyDecision,
    *,
    summary: OandaPracticeAccountSummarySnapshot,
    trades: OandaPracticeOpenTradeInventory,
    positions: OandaPracticeOpenPositionInventory,
    pricing: OandaPracticeEurUsdPricingObservation,
    config: RiskConfig,
    risk_service: RiskService | None = None,
) -> PaperRiskEvaluation:
    """Evaluate one supported opening proposal against supplied observations.

    All observations are caller-supplied normalized facts.  This operation has
    no external side effects and produces no broker instruction or durable state.
    """
    if type(strategy_decision) is not StrategyDecision:
        raise PaperRiskEvaluationError("strategy_decision must be a StrategyDecision")

    if strategy_decision.action is Action.NO_ACTION:
        return _result(
            PaperRiskOutcome.NO_ACTION,
            strategy_decision,
        )
    if strategy_decision.action in (
        Action.CLOSE_POSITION,
        Action.UPDATE_PROTECTION,
    ):
        return _result(
            PaperRiskOutcome.UNSUPPORTED_ACTION,
            strategy_decision,
        )
    if strategy_decision.entry_policy is EntryPolicy.PRICE_TRIGGERED:
        return _result(
            PaperRiskOutcome.DEFERRED_ENTRY_POLICY,
            strategy_decision,
        )
    if strategy_decision.entry_policy is not EntryPolicy.IMMEDIATE:
        raise PaperRiskEvaluationError(
            "opening decision has an unsupported entry policy"
        )
    direction = strategy_decision.direction
    stop = strategy_decision.stop
    target = strategy_decision.target
    decision_time = strategy_decision.decision_time
    if direction is None or stop is None or target is None or decision_time is None:
        raise PaperRiskEvaluationError("opening decision is missing Risk geometry")

    _require_observations(summary, trades, positions, pricing)
    if not _same_identity(summary, trades, positions, pricing):
        return _result(PaperRiskOutcome.IDENTITY_MISMATCH, strategy_decision)

    provenance = PaperObservationProvenance(
        provider=summary.identity.provider,
        environment=summary.identity.environment,
        provider_account_id=summary.identity.provider_account_id,
        base_currency=summary.identity.base_currency,
        price_time=pricing.price_time,
        summary_last_transaction_id=summary.last_transaction_id,
        trades_last_transaction_id=trades.last_transaction_id,
        positions_last_transaction_id=positions.last_transaction_id,
    )

    if summary.open_trade_count != len(
        trades.trades
    ) or summary.open_position_count != len(positions.positions):
        return _result(
            PaperRiskOutcome.OBSERVATION_MISMATCH,
            strategy_decision,
            provenance=provenance,
        )
    if summary.pending_order_count != 0:
        return _result(
            PaperRiskOutcome.ENTRY_STATE_BLOCKED,
            strategy_decision,
            provenance=provenance,
        )

    try:
        account = project_oanda_practice_account_state(summary)
        position = project_oanda_practice_eur_usd_exposure_state(trades, positions)
    except OandaExposureProjectionError:
        return _result(
            PaperRiskOutcome.OBSERVATION_MISMATCH,
            strategy_decision,
            provenance=provenance,
        )

    intent = TradeIntent(
        action=strategy_decision.action,
        direction=direction,
        stop=stop.price,
        target=target,
    )
    service = RiskService() if risk_service is None else risk_service
    pre_flight = service.evaluate_pre_flight(
        intent,
        position=position,
        account=account,
        config=config,
        instrument=Instrument.EUR_USD,
    )
    if not pre_flight.approved:
        return _result(
            PaperRiskOutcome.PRE_FLIGHT_REJECTED,
            strategy_decision,
            trade_intent=intent,
            pre_flight=pre_flight,
            provenance=provenance,
        )

    if pricing.price_time < decision_time:
        return _result(
            PaperRiskOutcome.PRICING_REJECTED,
            strategy_decision,
            trade_intent=intent,
            pre_flight=pre_flight,
            provenance=provenance,
        )

    projection = project_oanda_practice_executable_pricing(pricing, direction)
    candidate_evaluations = tuple(
        PaperCandidateRiskEvaluation(
            candidate=candidate,
            decision=service.evaluate_pre_submission_at_executable_price(
                intent,
                position=position,
                account=account,
                config=config,
                instrument=Instrument.EUR_USD,
                executable_price=ExecutablePrice(
                    price=candidate.price,
                    max_quantity=candidate.available_quantity,
                ),
            ),
        )
        for candidate in projection.candidates
    )
    pricing_evidence = PaperPricingEvidence(
        projection=projection,
        candidate_evaluations=candidate_evaluations,
    )
    if not candidate_evaluations:
        return _result(
            PaperRiskOutcome.PRICING_REJECTED,
            strategy_decision,
            trade_intent=intent,
            pre_flight=pre_flight,
            provenance=provenance,
            pricing_evidence=pricing_evidence,
        )

    approved = tuple(item for item in candidate_evaluations if item.decision.approved)
    if approved:
        selected = _select_adverse(approved, direction)
        pricing_evidence = PaperPricingEvidence(
            projection=projection,
            candidate_evaluations=candidate_evaluations,
            selected_candidate=selected.candidate,
        )
        return _result(
            PaperRiskOutcome.APPROVED,
            strategy_decision,
            trade_intent=intent,
            pre_flight=pre_flight,
            pre_submission=selected.decision,
            provenance=provenance,
            pricing_evidence=pricing_evidence,
        )

    if candidate_evaluations and all(
        item.decision.rejection is RiskRejection.INSUFFICIENT_EXECUTABLE_CAPACITY
        for item in candidate_evaluations
    ):
        return _result(
            PaperRiskOutcome.PRICING_REJECTED,
            strategy_decision,
            trade_intent=intent,
            pre_flight=pre_flight,
            provenance=provenance,
            pricing_evidence=pricing_evidence,
        )

    generic = tuple(
        item
        for item in candidate_evaluations
        if item.decision.rejection is not RiskRejection.INSUFFICIENT_EXECUTABLE_CAPACITY
    )
    representative = _select_adverse(generic, direction) if generic else None
    return _result(
        PaperRiskOutcome.PRE_SUBMISSION_REJECTED,
        strategy_decision,
        trade_intent=intent,
        pre_flight=pre_flight,
        pre_submission=representative.decision if representative else None,
        provenance=provenance,
        pricing_evidence=pricing_evidence,
    )


def _require_observations(
    summary: object,
    trades: object,
    positions: object,
    pricing: object,
) -> None:
    expected = (
        (summary, OandaPracticeAccountSummarySnapshot, "summary"),
        (trades, OandaPracticeOpenTradeInventory, "trades"),
        (positions, OandaPracticeOpenPositionInventory, "positions"),
        (pricing, OandaPracticeEurUsdPricingObservation, "pricing"),
    )
    for value, expected_type, name in expected:
        if type(value) is not expected_type:
            raise PaperRiskEvaluationError(
                f"{name} must be a normalized OANDA observation"
            )


def _identity_key(
    identity: OandaPracticeAccountIdentity,
) -> tuple[object, str, str, str]:
    return (
        identity.provider,
        identity.environment,
        identity.provider_account_id,
        identity.base_currency,
    )


def _same_identity(
    summary: OandaPracticeAccountSummarySnapshot,
    trades: OandaPracticeOpenTradeInventory,
    positions: OandaPracticeOpenPositionInventory,
    pricing: OandaPracticeEurUsdPricingObservation,
) -> bool:
    expected = _identity_key(summary.identity)
    return all(
        _identity_key(identity) == expected
        for identity in (
            trades.identity,
            positions.identity,
            pricing.identity,
        )
    )


def _select_adverse(
    evaluations: tuple[PaperCandidateRiskEvaluation, ...],
    direction: Direction,
) -> PaperCandidateRiskEvaluation:
    if not evaluations:
        raise PaperRiskEvaluationError("cannot select from empty pricing evidence")
    if direction is Direction.LONG:
        return max(
            evaluations,
            key=lambda item: (item.candidate.price, -item.candidate.available_quantity),
        )
    return min(
        evaluations,
        key=lambda item: (item.candidate.price, item.candidate.available_quantity),
    )


def _result(
    outcome: PaperRiskOutcome,
    strategy_decision: StrategyDecision,
    *,
    trade_intent: TradeIntent | None = None,
    pre_flight: RiskDecision | None = None,
    pre_submission: RiskDecision | None = None,
    provenance: PaperObservationProvenance | None = None,
    pricing_evidence: PaperPricingEvidence | None = None,
) -> PaperRiskEvaluation:
    return PaperRiskEvaluation(
        outcome=outcome,
        strategy_decision=strategy_decision,
        trade_intent=trade_intent,
        pre_flight=pre_flight,
        pre_submission=pre_submission,
        provenance=provenance,
        pricing_evidence=pricing_evidence,
    )


__all__ = [
    "PaperCandidateRiskEvaluation",
    "PaperObservationProvenance",
    "PaperPricingEvidence",
    "PaperRiskEvaluation",
    "PaperRiskEvaluationError",
    "PaperRiskOutcome",
    "evaluate_paper_risk",
]
