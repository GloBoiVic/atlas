"""EMA Sweep Confirmation Break: deterministic M15 setup state machine."""

from collections.abc import Sequence
from decimal import Decimal

from backend.domain.market_data import Bar, PriceComponent
from backend.domain.strategy import (
    Action,
    CandleFacts,
    Direction,
    EntryPolicy,
    ParameterError,
    ParameterSchema,
    Phase,
    PositionState,
    Rationale,
    SetupFacts,
    StopProposal,
    StrategyContext,
    StrategyDecision,
    StrategyEvaluation,
    StrategyParameters,
    StrategyState,
    TargetProposal,
)

from .contract import StrategyDefinition
from .indicators_v2 import atr, ema

DEFINITION = StrategyDefinition(
    strategy_key="ema_sweep_confirmation_break",
    name="EMA Sweep Confirmation Break",
    description="EUR/USD MID 15m EMA sweep with immediate confirmation break.",
    parameter_schema=(
        ParameterSchema(
            "ema_period",
            "EMA period",
            "integer",
            100,
            False,
            20,
            200,
            "EMA trend period",
        ),
        ParameterSchema(
            "atr_period", "ATR period", "integer", 14, False, 5, 50, "ATR stop period"
        ),
        ParameterSchema(
            "stop_buffer",
            "Stop buffer",
            "decimal",
            "0.5",
            False,
            "0.1",
            "3.0",
            "ATR multiplier",
        ),
        ParameterSchema(
            "target_r",
            "Target R",
            "decimal",
            "1.7",
            False,
            "0.5",
            "5.0",
            "Target risk multiple",
        ),
        ParameterSchema(
            "expiry_window",
            "Armed watch bars",
            "integer",
            5,
            False,
            5,
            5,
            "Subsequent completed M15 bars",
        ),
    ),
    capabilities=("LONG", "SHORT", "STOP_LOSS", "TAKE_PROFIT"),
    required_historical_context_bars=100,
    state_schema_version=2,
    source_files=(
        "backend/strategies/ema_sweep_confirmation_break.py",
        "backend/strategies/indicators_v2.py",
    ),
    # Pre-freeze v1 was never deployed; this corrected contract is the first
    # immutable version exposed by the production registry.
    implementation_key="ema_sweep_confirmation_break.v2",
)


def _facts(bar: Bar) -> CandleFacts:
    return CandleFacts(bar.end_time, bar.open, bar.high, bar.low, bar.close)


class EmaSweepConfirmationBreakStrategy:
    definition = DEFINITION

    @staticmethod
    def _validate_parameters(parameters: StrategyParameters) -> None:
        if (
            not 20 <= parameters.ema_period <= 200
            or not 5 <= parameters.atr_period <= 50
        ):
            raise ParameterError("EMA/ATR periods are outside supported bounds")
        if not Decimal("0.1") <= parameters.stop_buffer <= Decimal("3.0"):
            raise ParameterError("stop_buffer is outside supported bounds")
        if not Decimal("0.5") <= parameters.target_r <= Decimal("5.0"):
            raise ParameterError("target_r is outside supported bounds")
        if parameters.expiry_window != 5:
            raise ParameterError("expiry_window is fixed at five subsequent bars")

    def evaluate(
        self,
        context: StrategyContext,
        parameters: StrategyParameters,
        state: StrategyState,
    ) -> StrategyEvaluation:
        self._validate_parameters(parameters)
        current = context.bars[-1].end_time if context.bars else None
        if not context.exposure_allowed or context.position is not PositionState.FLAT:
            return StrategyEvaluation(
                StrategyDecision(Action.NO_ACTION, Rationale("EXPOSURE_NOT_ALLOWED")),
                StrategyState(schema_version=2, last_evaluated_bar_end=current),
            )
        if not context.bars:
            return StrategyEvaluation(
                StrategyDecision(Action.NO_ACTION, Rationale("NO_COMPLETED_BAR")), state
            )
        new = (
            context.bars
            if state.last_evaluated_bar_end is None
            else tuple(
                b for b in context.bars if b.end_time > state.last_evaluated_bar_end
            )
        )
        working, decision = (
            state,
            StrategyDecision(Action.NO_ACTION, Rationale("NO_SETUP")),
        )
        for bar in new:
            index = context.bars.index(bar)
            decision, working = self._step(
                bar, context.bars[: index + 1], working, parameters
            )
            if decision.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
                break
        if not new:
            working = StrategyState(schema_version=2, last_evaluated_bar_end=current)
        return StrategyEvaluation(decision, working)

    def _step(
        self,
        bar: Bar,
        history: Sequence[Bar],
        state: StrategyState,
        parameters: StrategyParameters,
    ) -> tuple[StrategyDecision, StrategyState]:
        if state.phase is Phase.ARMED:
            watched = state.watch_bars + 1
            # W5 is still eligible for execution observations.  Expiry is
            # observed only at the next completed analytical frontier (W6).
            if watched > parameters.expiry_window:
                return StrategyDecision(
                    Action.NO_ACTION, Rationale("SETUP_EXPIRED")
                ), StrategyState(schema_version=2, last_evaluated_bar_end=bar.end_time)
            return StrategyDecision(
                Action.NO_ACTION, Rationale("SETUP_ARMED")
            ), StrategyState(
                schema_version=state.schema_version,
                phase=Phase.ARMED,
                direction=state.direction,
                reference_high=state.reference_high,
                reference_low=state.reference_low,
                reference_time=state.reference_time,
                sweep_time=state.sweep_time,
                watch_bars=watched,
                confirmation_time=state.confirmation_time,
                trigger_price=state.trigger_price,
                last_evaluated_bar_end=bar.end_time,
            )
        if state.phase is Phase.REFERENCE_IDENTIFIED:
            assert (
                state.direction is not None
                and state.reference_high is not None
                and state.reference_low is not None
            )
            bullish, bearish = bar.close > bar.open, bar.close < bar.open
            if state.direction is Direction.LONG:
                valid = bullish and bar.low < state.reference_low
            else:
                valid = bearish and bar.high > state.reference_high
            if not valid:
                return StrategyDecision(
                    Action.NO_ACTION, Rationale("NO_SETUP")
                ), StrategyState(schema_version=2, last_evaluated_bar_end=bar.end_time)
            return self._open(bar, history, state, parameters)
        if len(history) < parameters.ema_period:
            return StrategyDecision(
                Action.NO_ACTION, Rationale("WARMING_UP")
            ), StrategyState(schema_version=2, last_evaluated_bar_end=bar.end_time)
        trend = ema(history, parameters.ema_period)
        direction = (
            Direction.SHORT
            if bar.close > bar.open and bar.close < trend
            else Direction.LONG
            if bar.close < bar.open and bar.close > trend
            else None
        )
        if direction is None:
            return StrategyDecision(
                Action.NO_ACTION, Rationale("NO_SETUP")
            ), StrategyState(schema_version=2, last_evaluated_bar_end=bar.end_time)
        return StrategyDecision(
            Action.NO_ACTION, Rationale("REFERENCE_IDENTIFIED")
        ), StrategyState(
            schema_version=2,
            phase=Phase.REFERENCE_IDENTIFIED,
            direction=direction,
            reference_high=bar.high,
            reference_low=bar.low,
            reference_time=bar.end_time,
            last_evaluated_bar_end=bar.end_time,
        )

    def _open(
        self,
        bar: Bar,
        history: Sequence[Bar],
        state: StrategyState,
        parameters: StrategyParameters,
    ) -> tuple[StrategyDecision, StrategyState]:
        assert (
            state.direction
            and state.reference_time
            and state.reference_high is not None
            and state.reference_low is not None
        )
        current_atr = atr(history, parameters.atr_period)
        reference_index = next(
            index
            for index, candidate in enumerate(history)
            if candidate.end_time == state.reference_time
        )
        reference_ema = ema(history[: reference_index + 1], parameters.ema_period)
        stop = (
            bar.low - parameters.stop_buffer * current_atr
            if state.direction is Direction.LONG
            else bar.high + parameters.stop_buffer * current_atr
        )
        trigger = (
            max(state.reference_high, bar.high)
            if state.direction is Direction.LONG
            else min(state.reference_low, bar.low)
        )
        facts = SetupFacts(
            _facts(next(x for x in history if x.end_time == state.reference_time)),
            _facts(bar),
            _facts(bar),
            "close_above_ema_at_reference"
            if state.direction is Direction.LONG
            else "close_below_ema_at_reference",
            current_atr,
            stop,
            trigger,
            reference_ema,
            "confirmation_low - (0.5 × ATR14)"
            if state.direction is Direction.LONG
            else "confirmation_high + (0.5 × ATR14)",
            "ASK" if state.direction is Direction.LONG else "BID",
        )
        decision = StrategyDecision(
            Action.OPEN_LONG
            if state.direction is Direction.LONG
            else Action.OPEN_SHORT,
            Rationale(
                "EMA_SWEEP_CONFIRMATION_BREAK_CONFIRMED",
                (("trigger_price", str(trigger)), ("stop_price", str(stop))),
            ),
            state.direction,
            bar.end_time,
            StopProposal(stop, state.direction),
            TargetProposal(multiple=parameters.target_r),
            EntryPolicy.PRICE_TRIGGERED,
            trigger,
            PriceComponent.ASK
            if state.direction is Direction.LONG
            else PriceComponent.BID,
            None,
            5,
            facts,
        )
        next_state = StrategyState(
            schema_version=2,
            phase=Phase.ARMED,
            direction=state.direction,
            reference_high=state.reference_high,
            reference_low=state.reference_low,
            reference_time=state.reference_time,
            sweep_time=bar.end_time,
            confirmation_time=bar.end_time,
            trigger_price=trigger,
            last_evaluated_bar_end=bar.end_time,
        )
        return decision, next_state


__all__ = ["DEFINITION", "EmaSweepConfirmationBreakStrategy"]
