class AtlasError(Exception):
    """Base exception for all Atlas errors."""


class BrokerError(AtlasError):
    """Broker connection or communication error."""


class OrderError(AtlasError):
    """Order placement or management error."""


class RiskError(AtlasError):
    """Risk limit violation."""


class StrategyError(AtlasError):
    """Strategy execution error."""


class DataError(AtlasError):
    """Market data retrieval error."""


class ConfigError(AtlasError):
    """Configuration validation error."""


class CircuitBreakerOpenError(AtlasError):
    """Raised when an operation is rejected by an open circuit breaker."""
