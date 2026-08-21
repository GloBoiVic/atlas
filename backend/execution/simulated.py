"""Pure deterministic historical execution; no clock, storage, or I/O."""

from dataclasses import dataclass
from decimal import Decimal

from .contract import (
    ExecutionObservation,
    ExecutionRejected,
    ExecutionRejection,
    Fill,
    Order,
)


@dataclass(frozen=True, slots=True)
class ProtectionDecision:
    fill: Fill | None
    ambiguous: bool = False
    ambiguity_policy: str | None = None


def _intrabar_touch(order: Order, observation: ExecutionObservation) -> bool:
    if observation.intrabar_trigger:
        return True
    price = order.requested_price
    assert price is not None
    ranges = (
        (observation.bid_high, observation.bid_low)
        if order.direction == "LONG"
        else (observation.ask_high, observation.ask_low)
    )
    high, low = ranges
    return (high is not None and high >= price) or (low is not None and low <= price)


class SimulatedExecutionAdapter:
    """Apply fixed adverse slippage to executable BID/ASK prices."""

    def __init__(
        self,
        *,
        slippage_ticks: int = 0,
        tick_size: Decimal = Decimal("0.00001"),
    ) -> None:
        if type(slippage_ticks) is not int or slippage_ticks < 0:
            raise ValueError("slippage_ticks must be a non-negative integer")
        if (
            type(tick_size) is not Decimal
            or not tick_size.is_finite()
            or tick_size <= 0
        ):
            raise ValueError("tick_size must be a positive Decimal")
        self.slippage = tick_size * slippage_ticks

    def execute(self, order: Order, observation: ExecutionObservation) -> Fill:
        if order.purpose == "ENTRY":
            price = (
                observation.ask_open if order.direction == "LONG"
                else observation.bid_open
            )
            return self._fill(order, observation, price, "OPEN")

        if order.purpose == "EXIT":
            reference = (
                observation.bid_close
                if order.direction == "LONG"
                else observation.ask_close
            )
            if reference is None:
                raise ValueError("END_CLOSE requires a BID/ASK close")
            return self._fill(order, observation, reference, "END_CLOSE")

        assert order.requested_price is not None
        quote = (
            observation.bid_open if order.direction == "LONG"
            else observation.ask_open
        )
        if order.purpose == "TAKE_PROFIT":
            reached = (
                quote >= order.requested_price
                if order.direction == "LONG"
                else quote <= order.requested_price
            )
            if reached:
                return self._fill(order, observation, order.requested_price, "OPEN")
            if _intrabar_touch(order, observation):
                return self._fill(
                    order, observation, order.requested_price, "INTRABAR_TARGET"
                )
            raise ExecutionRejected(ExecutionRejection.NOT_TRIGGERED)

        beyond_stop = (
            quote < order.requested_price
            if order.direction == "LONG"
            else quote > order.requested_price
        )
        if beyond_stop:
            return self._fill(order, observation, quote, "OPEN_GAP")
        if quote == order.requested_price:
            return self._fill(order, observation, order.requested_price, "OPEN")
        if _intrabar_touch(order, observation):
            return self._fill(
                order, observation, order.requested_price, "INTRABAR_STOP"
            )
        raise ExecutionRejected(ExecutionRejection.NOT_TRIGGERED)

    def execute_protection(
        self, stop: Order, target: Order, observation: ExecutionObservation
    ) -> ProtectionDecision:
        """Resolve a protection pair; stop wins an unknowable dual touch."""
        stop_touched = self._triggered(stop, observation)
        target_touched = self._triggered(target, observation)
        if not stop_touched and not target_touched:
            return ProtectionDecision(None)
        if stop_touched:
            fill = self.execute(stop, observation)
            return ProtectionDecision(
                fill,
                target_touched,
                "STOP_LOSS_ADVERSE_FIRST_V1" if target_touched else None,
            )
        return ProtectionDecision(self.execute(target, observation))

    @staticmethod
    def _triggered(order: Order, observation: ExecutionObservation) -> bool:
        if order.purpose == "TAKE_PROFIT":
            quote = (
                observation.bid_open
                if order.direction == "LONG"
                else observation.ask_open
            )
            if (
                quote >= order.requested_price
                if order.direction == "LONG"
                else quote <= order.requested_price
            ):
                return True
        return _intrabar_touch(order, observation)

    def _fill(
        self,
        order: Order,
        observation: ExecutionObservation,
        reference: Decimal,
        basis: str,
    ) -> Fill:
        # Entry buys/sells worse by direction; liquidation is the inverse.
        if order.purpose == "ENTRY":
            price = (
                reference + self.slippage
                if order.direction == "LONG"
                else reference - self.slippage
            )
        elif order.purpose == "EXIT":
            price = (
                reference - self.slippage
                if order.direction == "LONG"
                else reference + self.slippage
            )
        elif order.purpose == "STOP_LOSS":
            price = (
                reference - self.slippage
                if order.direction == "LONG"
                else reference + self.slippage
            )
        else:
            price = reference
        if price <= 0:
            raise ValueError("slippage produced a non-positive execution price")
        source = (
            observation.ask_source_market_bar_id
            if order.direction == "LONG" and order.purpose == "ENTRY"
            else observation.bid_source_market_bar_id
        )
        if order.purpose != "ENTRY":
            source = (
                observation.bid_source_market_bar_id
                if order.direction == "LONG"
                else observation.ask_source_market_bar_id
            )
        applied = self.slippage if price != reference else Decimal("0")
        return Fill(
            order.id,
            1,
            order.quantity,
            price,
            observation.observed_at,
            Decimal("0"),
            source,
            basis,
            reference,
            applied,
            applied * order.quantity,
        )

    @staticmethod
    def _not_triggered() -> Fill:
        raise ExecutionRejected(ExecutionRejection.NOT_TRIGGERED)


__all__ = ["ProtectionDecision", "SimulatedExecutionAdapter"]
