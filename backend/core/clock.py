from abc import ABC, abstractmethod
from datetime import UTC, datetime


class Clock(ABC):
    """Source of the current time for trading components."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current timestamp."""


class LiveClock(Clock):
    """Clock that reads the current UTC time from the system clock."""

    def now(self) -> datetime:
        """Return the current system time as a UTC-aware timestamp."""
        return datetime.now(UTC)


class SimulationClock(Clock):
    """Clock whose current time is controlled by the backtest."""

    def __init__(self, start_time: datetime) -> None:
        """Initialize the clock at ``start_time``."""
        self._current_time = start_time

    def now(self) -> datetime:
        """Return the current simulated timestamp."""
        return self._current_time

    def advance(self, new_time: datetime) -> None:
        """Set the simulated timestamp to ``new_time`` exactly."""
        self._current_time = new_time
