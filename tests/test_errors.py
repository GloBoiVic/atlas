import pytest

from backend.core.errors import (
    AtlasError,
    BrokerError,
    ConfigError,
    DataError,
    OrderError,
    RiskError,
    StrategyError,
)


def test_atlas_error_is_base():
    assert issubclass(BrokerError, AtlasError)
    assert issubclass(OrderError, AtlasError)
    assert issubclass(RiskError, AtlasError)
    assert issubclass(StrategyError, AtlasError)
    assert issubclass(DataError, AtlasError)
    assert issubclass(ConfigError, AtlasError)


def test_errors_can_be_raised():
    with pytest.raises(BrokerError):
        raise BrokerError("connection failed")

    with pytest.raises(OrderError):
        raise OrderError("order rejected")
