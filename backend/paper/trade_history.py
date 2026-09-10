"""Read-only composition of completed PAPER Trade history."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.persistence.models import (
    PaperBrokerObservationModel,
    PaperExecutionAttemptModel,
    StrategyModel,
    StrategyVersionModel,
)

from .execution import BrokerFillFacts
from .persistence_contracts import (
    PAPER_BROKER_FACTS_SCHEMA_V2,
    PaperTradeCloseTransaction,
    PaperTradeClosure,
    PaperTradeExitCause,
    ReconciliationStatus,
)


class PaperTradeHistoryReadError(ValueError):
    """A requested PAPER Trade history read cannot be performed safely."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PaperTradeHistoryItem:
    """Trader-facing facts composed from immutable PAPER evidence."""

    strategy_key: str
    strategy_name: str
    strategy_version_number: int
    instrument: str
    direction: str
    units: str
    entry_price: str
    entered_at: str
    stop_price: str | None
    target_price: str | None
    initial_risk: str | None
    closed_at: str
    average_close_price: str
    realized_pl: str
    financing: str
    dividend_adjustment: str
    exit_cause: str | None

    def to_json(self) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "strategy_name": self.strategy_name,
            "strategy_version_number": self.strategy_version_number,
            "instrument": self.instrument,
            "direction": self.direction,
            "units": self.units,
            "entry_price": self.entry_price,
            "entered_at": self.entered_at,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "initial_risk": self.initial_risk,
            "closed_at": self.closed_at,
            "average_close_price": self.average_close_price,
            "realized_pl": self.realized_pl,
            "financing": self.financing,
            "dividend_adjustment": self.dividend_adjustment,
            "exit_cause": self.exit_cause,
        }


class PaperTradeHistoryReadService:
    """Compose a bounded completed-Trade view without provider access."""

    def list(
        self, session: Session, limit: int = 10
    ) -> tuple[PaperTradeHistoryItem, ...]:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise PaperTradeHistoryReadError(
                "INVALID_LIMIT", "limit must be between 1 and 50"
            )

        # Apply the API limit only after parsed eligibility and chronology are known.
        statement = (
            select(
                PaperExecutionAttemptModel,
                StrategyModel,
                PaperBrokerObservationModel,
            )
            .join(
                StrategyVersionModel,
                StrategyVersionModel.id
                == PaperExecutionAttemptModel.strategy_version_id,
            )
            .join(
                StrategyModel,
                StrategyModel.id == StrategyVersionModel.strategy_id,
            )
            .join(
                PaperBrokerObservationModel,
                PaperBrokerObservationModel.attempt_id
                == PaperExecutionAttemptModel.attempt_id,
            )
            .where(
                PaperExecutionAttemptModel.reconciliation_status
                == ReconciliationStatus.LIFECYCLE_ADVANCED.value,
                PaperExecutionAttemptModel.fill_broker_order_id.is_not(None),
                PaperExecutionAttemptModel.fill_transaction_id.is_not(None),
                PaperExecutionAttemptModel.fill_trade_id.is_not(None),
                PaperExecutionAttemptModel.fill_signed_units.is_not(None),
                PaperExecutionAttemptModel.fill_price.is_not(None),
                PaperExecutionAttemptModel.fill_executed_at.is_not(None),
                PaperExecutionAttemptModel.fill_actual_initial_risk.is_not(None),
                PaperBrokerObservationModel.normalized_schema_version
                == PAPER_BROKER_FACTS_SCHEMA_V2,
                PaperBrokerObservationModel.read_kind == "TRADE_DETAIL",
                PaperBrokerObservationModel.object_kind == "TRADE",
            )
        )
        rows = session.execute(statement).all()

        grouped: dict[
            UUID,
            tuple[
                PaperExecutionAttemptModel,
                StrategyModel,
                list[PaperBrokerObservationModel],
            ],
        ] = {}
        for attempt, strategy, observation in rows:
            if (
                attempt.reconciliation_status
                != ReconciliationStatus.LIFECYCLE_ADVANCED.value
            ):
                continue
            if (
                observation.normalized_schema_version != PAPER_BROKER_FACTS_SCHEMA_V2
                or observation.read_kind != "TRADE_DETAIL"
                or observation.object_kind != "TRADE"
            ):
                continue
            current = grouped.get(attempt.attempt_id)
            if current is None:
                grouped[attempt.attempt_id] = (attempt, strategy, [observation])
            else:
                current[2].append(observation)

        if not grouped:
            return ()

        attempt_ids = tuple(grouped)
        transaction_statement = select(PaperBrokerObservationModel).where(
            PaperBrokerObservationModel.attempt_id.in_(attempt_ids),
            PaperBrokerObservationModel.normalized_schema_version
            == PAPER_BROKER_FACTS_SCHEMA_V2,
            PaperBrokerObservationModel.read_kind == "TRANSACTION_DETAIL",
            PaperBrokerObservationModel.object_kind == "TRANSACTION",
        )
        transaction_rows = session.scalars(transaction_statement).all()
        transactions_by_attempt: dict[UUID, list[PaperBrokerObservationModel]] = (
            defaultdict(list)
        )
        for observation in transaction_rows:
            if (
                observation.normalized_schema_version != PAPER_BROKER_FACTS_SCHEMA_V2
                or observation.read_kind != "TRANSACTION_DETAIL"
                or observation.object_kind != "TRANSACTION"
            ):
                continue
            transactions_by_attempt[observation.attempt_id].append(observation)

        composed: list[tuple[datetime, str, PaperTradeHistoryItem]] = []
        for attempt, strategy, observations in grouped.values():
            fill = _fill(attempt)
            if fill is None:
                continue
            closure = _closure_for_fill(observations, fill)
            if closure is None:
                continue
            item = _item(
                attempt,
                strategy,
                fill,
                closure,
                _exact_exit_cause(
                    transactions_by_attempt.get(attempt.attempt_id, ()), closure
                ),
            )
            composed.append((closure.closed_at, str(attempt.attempt_id), item))

        composed.sort(key=lambda value: (value[0], value[1]), reverse=True)
        return tuple(item for _, _, item in composed[:limit])


def _fill(row: PaperExecutionAttemptModel) -> BrokerFillFacts | None:
    values = (
        row.fill_broker_order_id,
        row.fill_transaction_id,
        row.fill_trade_id,
        row.fill_signed_units,
        row.fill_price,
        row.fill_executed_at,
        row.fill_actual_initial_risk,
    )
    if any(value is None for value in values):
        return None
    try:
        return BrokerFillFacts(
            broker_order_id=cast(str, values[0]),
            broker_fill_transaction_id=cast(str, values[1]),
            broker_trade_id=cast(str, values[2]),
            signed_units=cast(Decimal, values[3]),
            price=cast(Decimal, values[4]),
            executed_at=cast(datetime, values[5]),
            actual_initial_risk=cast(Decimal, values[6]),
        )
    except Exception:
        return None


def _closure_for_fill(
    observations: list[PaperBrokerObservationModel], fill: BrokerFillFacts
) -> PaperTradeClosure | None:
    closures: list[PaperTradeClosure] = []
    malformed = False
    for observation in observations:
        facts = _facts(observation.normalized_facts)
        if facts is None:
            continue
        if facts.get("trade_id") != fill.broker_trade_id:
            continue
        if (
            observation.provider_trade_id is not None
            and observation.provider_trade_id != fill.broker_trade_id
        ):
            continue
        if facts.get("state") != "CLOSED":
            continue
        try:
            closures.append(_parse_closure(facts))
        except (TypeError, ValueError):
            malformed = True

    if malformed or not closures:
        return None
    first = closures[0]
    if any(closure != first for closure in closures[1:]):
        return None
    return first


def _parse_closure(facts: Mapping[str, object]) -> PaperTradeClosure:
    trade_id = _text(facts.get("trade_id"), "trade_id", maximum=128)
    close_time = _timestamp(facts.get("close_time"), "close_time")
    closing_ids_value = facts.get("closing_transaction_ids")
    if type(closing_ids_value) is not list or not closing_ids_value:
        raise ValueError("closing_transaction_ids is invalid")
    closing_ids_raw = cast(list[object], closing_ids_value)
    if len(closing_ids_raw) > 64:
        raise ValueError("closing_transaction_ids is too large")
    closing_ids = tuple(
        _text(value, "closing_transaction_id", maximum=128) for value in closing_ids_raw
    )
    if len(set(closing_ids)) != len(closing_ids):
        raise ValueError("closing_transaction_ids are not unique")
    return PaperTradeClosure(
        trade_id=trade_id,
        closed_at=close_time,
        average_close_price=_decimal(
            facts.get("average_close_price"), "average_close_price", positive=True
        ),
        realized_pl=_decimal(facts.get("realized_pl"), "realized_pl"),
        financing=_decimal(facts.get("financing"), "financing"),
        dividend_adjustment=_decimal(
            facts.get("dividend_adjustment"), "dividend_adjustment"
        ),
        closing_transaction_ids=closing_ids,
        exit_cause=(
            PaperTradeExitCause.MULTIPLE
            if len(closing_ids) > 1
            else PaperTradeExitCause.UNRESOLVED
        ),
    )


def _exact_exit_cause(
    observations: Sequence[PaperBrokerObservationModel], closure: PaperTradeClosure
) -> str | None:
    if len(closure.closing_transaction_ids) != 1:
        return None
    transaction_id = closure.closing_transaction_ids[0]
    causes: list[PaperTradeExitCause] = []
    malformed = False
    for observation in observations:
        facts = _facts(observation.normalized_facts)
        if facts is None:
            continue
        if facts.get("transaction_id") != transaction_id:
            continue
        if facts.get("closed_trade_id") != closure.trade_id:
            continue
        if (
            observation.provider_transaction_id is not None
            and observation.provider_transaction_id != transaction_id
        ):
            continue
        if (
            observation.provider_trade_id is not None
            and observation.provider_trade_id != closure.trade_id
        ):
            continue
        try:
            causes.append(_parse_close_transaction(facts).exit_cause)
        except (TypeError, ValueError):
            malformed = True

    if malformed or not causes or any(cause != causes[0] for cause in causes[1:]):
        return None
    cause = causes[0]
    if cause in {PaperTradeExitCause.UNRESOLVED, PaperTradeExitCause.MULTIPLE}:
        return None
    return cause.value


def _parse_close_transaction(
    facts: Mapping[str, object],
) -> PaperTradeCloseTransaction:
    provider_reason_value = facts.get("provider_reason")
    provider_reason = (
        None
        if provider_reason_value is None
        else _text(provider_reason_value, "provider_reason", maximum=128)
    )
    cause_value = facts.get("exit_cause")
    if type(cause_value) is not str:
        raise ValueError("exit_cause is invalid")
    try:
        cause = PaperTradeExitCause(cause_value)
    except ValueError as error:
        raise ValueError("exit_cause is invalid") from error
    return PaperTradeCloseTransaction(
        transaction_id=_text(facts.get("transaction_id"), "transaction_id", maximum=64),
        trade_id=_text(facts.get("closed_trade_id"), "closed_trade_id", maximum=128),
        closed_units=_decimal(facts.get("closed_units"), "closed_units"),
        close_price=_decimal(facts.get("close_price"), "close_price", positive=True),
        realized_pl=_decimal(facts.get("close_realized_pl"), "close_realized_pl"),
        financing=_decimal(facts.get("close_financing"), "close_financing"),
        provider_reason=provider_reason,
        exit_cause=cause,
    )


def _item(
    attempt: PaperExecutionAttemptModel,
    strategy: StrategyModel,
    fill: BrokerFillFacts,
    closure: PaperTradeClosure,
    exit_cause: str | None,
) -> PaperTradeHistoryItem:
    return PaperTradeHistoryItem(
        strategy_key=attempt.strategy_key,
        strategy_name=strategy.name,
        strategy_version_number=attempt.strategy_version_number,
        instrument=attempt.instrument,
        direction=attempt.direction,
        units=str(abs(fill.signed_units)),
        entry_price=str(fill.price),
        entered_at=_timestamp_text(fill.executed_at),
        stop_price=_confirmed_price(attempt.stop_loss_status, attempt.stop_loss_price),
        target_price=_confirmed_price(
            attempt.take_profit_status, attempt.take_profit_price
        ),
        initial_risk=str(fill.actual_initial_risk),
        closed_at=_timestamp_text(closure.closed_at),
        average_close_price=str(closure.average_close_price),
        realized_pl=str(closure.realized_pl),
        financing=str(closure.financing),
        dividend_adjustment=str(closure.dividend_adjustment),
        exit_cause=exit_cause,
    )


def _confirmed_price(status: object, value: object) -> str | None:
    if status != "CONFIRMED" or type(value) is not Decimal:
        return None
    if not value.is_finite() or value <= 0:
        return None
    return str(value)


def _facts(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return cast(Mapping[str, object], value)


def _text(value: object, name: str, *, maximum: int) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise ValueError(f"{name} is invalid")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{name} contains control characters")
    return value


def _decimal(value: object, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not str:
        raise ValueError(f"{name} is invalid")
    try:
        parsed = Decimal(value)
    except Exception as error:
        raise ValueError(f"{name} is invalid") from error
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise ValueError(f"{name} is invalid")
    return parsed


def _timestamp(value: object, name: str) -> datetime:
    if type(value) is not str:
        raise ValueError(f"{name} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed.astimezone(UTC)


def _timestamp_text(value: datetime) -> str:
    instant = (
        value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    )
    return instant.isoformat().replace("+00:00", "Z")


__all__ = [
    "PaperTradeHistoryItem",
    "PaperTradeHistoryReadError",
    "PaperTradeHistoryReadService",
]
