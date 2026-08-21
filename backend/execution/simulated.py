"""The deliberately narrow, pure Phase 3 simulated execution adapter."""

from .contract import (
    ExecutionObservation,
    ExecutionRejected,
    ExecutionRejection,
    Fill,
    Order,
)


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
    """Convert an Order and reduced observation into one full Fill.

    This class has no session, repository, clock, or mutable state.  It only
    describes what the Phase 3 checkpoint can prove at an M1 open.
    """

    def execute(self, order: Order, observation: ExecutionObservation) -> Fill:
        if order.purpose == "ENTRY":
            price = (
                observation.ask_open if order.direction == "LONG"
                else observation.bid_open
            )
            return Fill(order.id, 1, order.quantity, price, observation.observed_at)

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
                return Fill(
                    order.id, 1, order.quantity, order.requested_price,
                    observation.observed_at,
                )
            raise ExecutionRejected(
                ExecutionRejection.UNSUPPORTED_PHASE3_INTRABAR_TRIGGER
            )

        beyond_stop = (
            quote < order.requested_price
            if order.direction == "LONG"
            else quote > order.requested_price
        )
        if beyond_stop:
            raise ExecutionRejected(ExecutionRejection.UNSUPPORTED_PHASE3_STOP_GAP)
        if quote == order.requested_price:
            return Fill(
                order.id, 1, order.quantity, order.requested_price,
                observation.observed_at,
            )
        if _intrabar_touch(order, observation):
            raise ExecutionRejected(
                ExecutionRejection.UNSUPPORTED_PHASE3_INTRABAR_TRIGGER
            )
        return self._not_triggered()

    @staticmethod
    def _not_triggered() -> Fill:
        raise ExecutionRejected(ExecutionRejection.UNSUPPORTED_PHASE3_INTRABAR_TRIGGER)


__all__ = ["SimulatedExecutionAdapter"]
