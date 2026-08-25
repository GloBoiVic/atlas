"""Parameter-enabled EMA Sweep Engulfing Strategy v2.

The v1 implementation is intentionally not imported or modified.  This source
keeps its five-bar setup frontier and completed-bar evaluation semantics while
making the four approved values runtime parameters.
"""

from collections.abc import Sequence
from decimal import Decimal

from backend.domain.market_data import Bar
from backend.domain.strategy import (
    Action,
    Direction,
    ParameterError,
    ParameterSchema,
    Phase,
    PositionState,
    Rationale,
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


def _schema() -> tuple[ParameterSchema, ...]:
    return (
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
            "ATR stop buffer multiplier",
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
            "Confirmation window",
            "integer",
            5,
            False,
            5,
            5,
            "Received-bar confirmation window",
        ),
    )


DEFINITION = StrategyDefinition(
    strategy_key="ema_sweep_engulfing",
    name="EMA Sweep Engulfing",
    description="EUR/USD MID 15m parameter-enabled EMA Sweep Engulfing strategy.",
    parameter_schema=_schema(),
    capabilities=("LONG", "SHORT", "STOP_LOSS", "TAKE_PROFIT"),
    required_historical_context_bars=200,
    state_schema_version=1,
    source_files=(
        "backend/strategies/ema_sweep_engulfing_v2.py",
        "backend/strategies/indicators_v2.py",
    ),
    implementation_key="ema_sweep_engulfing.v2",
)


class EmaSweepEngulfingV2Strategy:
    definition = DEFINITION

    def evaluate(
        self,
        context: StrategyContext,
        parameters: StrategyParameters,
        state: StrategyState,
    ) -> StrategyEvaluation:
        self._validate_parameters(parameters)
        if not context.exposure_allowed or context.position is not PositionState.FLAT:
            current_end = context.bars[-1].end_time if context.bars else None
            return StrategyEvaluation(
                StrategyDecision(Action.NO_ACTION, Rationale("EXPOSURE_NOT_ALLOWED")),
                StrategyState(last_evaluated_bar_end=current_end),
            )
        if not context.bars:
            return StrategyEvaluation(
                StrategyDecision(Action.NO_ACTION, Rationale("NO_COMPLETED_BAR")), state
            )
        current_end = context.bars[-1].end_time
        new_bars = (
            context.bars
            if state.last_evaluated_bar_end is None
            else tuple(
                bar
                for bar in context.bars
                if bar.end_time > state.last_evaluated_bar_end
            )
        )
        working = state
        decision = StrategyDecision(Action.NO_ACTION, Rationale("NO_SETUP"))
        for bar in new_bars:
            index = context.bars.index(bar)
            decision, working = self._step(
                bar, context.bars[: index + 1], working, parameters
            )
            if decision.action in (Action.OPEN_LONG, Action.OPEN_SHORT):
                break
        if not new_bars:
            working = StrategyState(last_evaluated_bar_end=current_end)
        return StrategyEvaluation(decision, working)

    @staticmethod
    def _validate_parameters(parameters: StrategyParameters) -> None:
        if not 20 <= parameters.ema_period <= 200:
            raise ParameterError("ema_period must be an integer from 20 through 200")
        if not 5 <= parameters.atr_period <= 50:
            raise ParameterError("atr_period must be an integer from 5 through 50")
        if not Decimal("0.1") <= parameters.stop_buffer <= Decimal("3.0"):
            raise ParameterError("stop_buffer must be between 0.1 and 3.0")
        if not Decimal("0.5") <= parameters.target_r <= Decimal("5.0"):
            raise ParameterError("target_r must be between 0.5 and 5.0")
        if parameters.expiry_window != 5:
            raise ParameterError("expiry_window is fixed at five received bars")

    def _step(
        self,
        bar: Bar,
        history: Sequence[Bar],
        state: StrategyState,
        parameters: StrategyParameters,
    ) -> tuple[StrategyDecision, StrategyState]:
        if state.phase is Phase.SEARCHING:
            if len(history) < 20:
                return StrategyDecision(
                    Action.NO_ACTION, Rationale("WARMING_UP")
                ), StrategyState(last_evaluated_bar_end=bar.end_time)
            trend = ema(history, parameters.ema_period)
            if bar.close > bar.open and bar.close < trend:
                return StrategyDecision(
                    Action.NO_ACTION, Rationale("REFERENCE_IDENTIFIED")
                ), StrategyState(
                    phase=Phase.REFERENCE_IDENTIFIED,
                    direction=Direction.SHORT,
                    reference_high=bar.high,
                    reference_low=bar.low,
                    reference_time=bar.end_time,
                    last_evaluated_bar_end=bar.end_time,
                )
            if bar.close < bar.open and bar.close > trend:
                return StrategyDecision(
                    Action.NO_ACTION, Rationale("REFERENCE_IDENTIFIED")
                ), StrategyState(
                    phase=Phase.REFERENCE_IDENTIFIED,
                    direction=Direction.LONG,
                    reference_high=bar.high,
                    reference_low=bar.low,
                    reference_time=bar.end_time,
                    last_evaluated_bar_end=bar.end_time,
                )
            return StrategyDecision(
                Action.NO_ACTION, Rationale("NO_SETUP")
            ), StrategyState(last_evaluated_bar_end=bar.end_time)
        window = state.window_bars + 1
        assert (
            state.direction is not None
            and state.reference_high is not None
            and state.reference_low is not None
            and state.reference_time is not None
        )
        if state.direction is Direction.LONG:
            sweep = bar.close > bar.open and bar.low < state.reference_low
            confirmation = bar.close > state.reference_high and bar.close > bar.open
            if sweep and confirmation:
                return self._open(bar, history, Direction.LONG, state, parameters)
            if sweep:
                phase, sweep_time = Phase.AWAITING_CONFIRMATION, bar.end_time
            else:
                phase, sweep_time = state.phase, state.sweep_time
            if state.phase is Phase.AWAITING_CONFIRMATION and confirmation:
                return self._open(bar, history, Direction.LONG, state, parameters)
        else:
            sweep = bar.close < bar.open and bar.high > state.reference_high
            confirmation = bar.close < state.reference_low and bar.close < bar.open
            if sweep and confirmation:
                return self._open(bar, history, Direction.SHORT, state, parameters)
            if sweep:
                phase, sweep_time = Phase.AWAITING_CONFIRMATION, bar.end_time
            else:
                phase, sweep_time = state.phase, state.sweep_time
            if state.phase is Phase.AWAITING_CONFIRMATION and confirmation:
                return self._open(bar, history, Direction.SHORT, state, parameters)
        if window >= 5:
            return StrategyDecision(
                Action.NO_ACTION, Rationale("SETUP_EXPIRED")
            ), StrategyState(last_evaluated_bar_end=bar.end_time)
        return StrategyDecision(
            Action.NO_ACTION, Rationale("SETUP_PENDING")
        ), StrategyState(
            phase=phase,
            direction=state.direction,
            reference_high=state.reference_high,
            reference_low=state.reference_low,
            reference_time=state.reference_time,
            sweep_time=sweep_time,
            window_bars=window,
            last_evaluated_bar_end=bar.end_time,
        )

    @staticmethod
    def _open(
        bar: Bar,
        history: Sequence[Bar],
        direction: Direction,
        state: StrategyState,
        parameters: StrategyParameters,
    ) -> tuple[StrategyDecision, StrategyState]:
        assert state.reference_time is not None
        current_atr = atr(history, parameters.atr_period)
        sweep_bar = (
            bar
            if state.sweep_time is None
            else next(
                candidate
                for candidate in history
                if candidate.end_time == state.sweep_time
            )
        )
        stop_price = (
            bar.low - parameters.stop_buffer * current_atr
            if direction is Direction.LONG
            else bar.high + parameters.stop_buffer * current_atr
        )
        trend_relation = (
            f"close_above_ema_{parameters.ema_period}_at_reference"
            if direction is Direction.LONG
            else f"close_below_ema_{parameters.ema_period}_at_reference"
        )
        stop_structure = (
            "confirmation_low - (stop_buffer * ATR)"
            if direction is Direction.LONG
            else "confirmation_high + (stop_buffer * ATR)"
        )
        rationale = Rationale(
            "EMA_SWEEP_ENGULFING_CONFIRMED",
            (
                ("trend_relation", trend_relation),
                ("reference_time", state.reference_time.isoformat()),
                ("reference_high", str(state.reference_high)),
                ("reference_low", str(state.reference_low)),
                ("sweep_time", (state.sweep_time or bar.end_time).isoformat()),
                ("sweep_high", str(sweep_bar.high)),
                ("sweep_low", str(sweep_bar.low)),
                ("confirmation_time", bar.end_time.isoformat()),
                ("confirmation_high", str(bar.high)),
                ("confirmation_low", str(bar.low)),
                ("atr", str(current_atr)),
                ("stop_buffer", str(parameters.stop_buffer)),
                ("stop_structure", stop_structure),
                ("stop_price", str(stop_price)),
            ),
        )
        return StrategyDecision(
            Action.OPEN_LONG if direction is Direction.LONG else Action.OPEN_SHORT,
            rationale,
            direction,
            bar.end_time,
            StopProposal(stop_price, direction),
            TargetProposal(multiple=parameters.target_r),
        ), StrategyState(last_evaluated_bar_end=bar.end_time)


__all__ = ["DEFINITION", "EmaSweepEngulfingV2Strategy"]
