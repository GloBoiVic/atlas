"""Per-bot strategy evaluation and completed-candle signal gating."""

from collections.abc import Sequence
from datetime import datetime
from typing import cast
from uuid import UUID

from backend.core.events import (
    CandleClosed,
    EventBus,
    EventHandler,
    SignalGenerated,
    StrategyError,
    Subscription,
)
from backend.data.models import Candle
from backend.strategy.base import Strategy
from backend.strategy.contracts import DataRequirement, DataType, Signal, StrategyDecision

type CandleKey = tuple[UUID, str, str, datetime, str]


class StrategyEngine:
    """Evaluate completed candles for one isolated bot strategy instance."""

    def __init__(
        self,
        event_bus: EventBus,
        bot_id: UUID,
        account_id: UUID,
        instrument_id: UUID,
        strategy: Strategy,
        strategy_version_id: UUID,
        strategy_name: str,
        commit_sha: str,
        data_requirement: DataRequirement,
    ) -> None:
        if data_requirement.data_type is not DataType.CANDLE:
            raise ValueError("StrategyEngine requires a candle DataRequirement")

        self._event_bus = event_bus
        self._bot_id = bot_id
        self._account_id = account_id
        self._instrument_id = instrument_id
        self._strategy = strategy
        self._strategy_version_id = strategy_version_id
        self._strategy_name = strategy_name
        self._commit_sha = commit_sha
        self._data_requirement = data_requirement
        self._warmed_up = False
        self._seen_candle_keys: set[CandleKey] = set()
        self._subscription: Subscription = event_bus.subscribe(
            CandleClosed,
            cast("EventHandler", self._on_candle),
        )

    @staticmethod
    def _candle_key(candle: Candle) -> CandleKey:
        """Return the candle's provider-domain composite identity, not a row ID."""
        return (
            candle.instrument_id,
            candle.provider,
            candle.timeframe,
            candle.open_time,
            candle.price_basis,
        )

    @staticmethod
    def _valid_candle(candle: object, instrument_id: UUID, timeframe: str) -> bool:
        return (
            isinstance(candle, Candle)
            and candle.instrument_id == instrument_id
            and candle.timeframe == timeframe
            and candle.is_complete
        )

    async def warm_up(self, candles: Sequence[Candle]) -> None:
        """Rebuild strategy state from ordered candles without emitting signals.

        The caller owns sourcing and ordering. Invalid or duplicate candles are ignored using
        the same validation and composite deduplication rules as live candle events.
        """
        for candle in candles:
            if not self._valid_candle(
                candle,
                self._instrument_id,
                self._data_requirement.timeframe,
            ):
                continue
            key = self._candle_key(candle)
            if key in self._seen_candle_keys:
                continue
            self._seen_candle_keys.add(key)
            try:
                decision = self._strategy.on_candle(candle)
                if decision is not None and not isinstance(decision, StrategyDecision):
                    raise TypeError("strategy on_candle must return a StrategyDecision or None")
            except Exception as exception:
                await self._publish_strategy_error(exception, None)
                raise
        self._warmed_up = True

    async def _on_candle(self, event: CandleClosed) -> None:
        if not self._warmed_up or not isinstance(event.candle, Candle):
            return

        candle = event.candle
        if not self._valid_candle(candle, self._instrument_id, self._data_requirement.timeframe):
            return
        key = self._candle_key(candle)
        if key in self._seen_candle_keys:
            return
        self._seen_candle_keys.add(key)

        try:
            decision = self._strategy.on_candle(candle)
            if decision is not None and not isinstance(decision, StrategyDecision):
                raise TypeError("strategy on_candle must return a StrategyDecision or None")
            signal = self._signal_from_decision(decision, candle) if decision is not None else None
        except Exception as exception:
            await self._publish_strategy_error(exception, event)
            raise

        if signal is None:
            return
        await self._event_bus.publish(
            SignalGenerated(
                signal=signal,
                account_id=self._account_id,
                bot_id=self._bot_id,
                mode=event.mode,
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
            )
        )

    async def _publish_strategy_error(
        self, exception: Exception, event: CandleClosed | None
    ) -> None:
        if event is not None:
            error = StrategyError(
                error=str(exception),
                account_id=self._account_id,
                bot_id=self._bot_id,
                mode=event.mode,
                correlation_id=event.correlation_id,
            )
        else:
            error = StrategyError(
                error=str(exception),
                account_id=self._account_id,
                bot_id=self._bot_id,
            )
        await self._event_bus.publish(error)

    def _signal_from_decision(self, decision: StrategyDecision, candle: Candle) -> Signal:
        return Signal(
            instrument_id=self._instrument_id,
            direction=decision.direction,
            strength=decision.strength,
            metadata=decision.metadata,
            candle_timestamp=candle.open_time,
            strategy_version_id=self._strategy_version_id,
            strategy_name=self._strategy_name,
            strategy_commit_sha=self._commit_sha,
        )

    def unsubscribe(self) -> None:
        """Remove this engine's candle subscription."""
        self._subscription.unsubscribe()

    def close(self) -> None:
        """Release subscriptions owned by this engine."""
        self.unsubscribe()
