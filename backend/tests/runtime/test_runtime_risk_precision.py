from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import Numeric

from backend.api.schemas import PaperActivationRequest as PaperActivationHttpRequest
from backend.persistence.models import PaperRuntimeActivationModel
from backend.runtime import PaperActivationRequest

ACTIVATION_ID = UUID("11111111-1111-1111-1111-111111111111")
VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_runtime_risk_storage_is_unconstrained_decimal() -> None:
    risk_type = PaperRuntimeActivationModel.__table__.c.risk_per_trade.type

    assert isinstance(risk_type, Numeric)
    assert risk_type.precision is None
    assert risk_type.scale is None
    assert risk_type.asdecimal is True


@pytest.mark.parametrize(
    "risk_text",
    ("0.01", "0.12345678901", "0.00000000001"),
)
def test_activation_accepts_exact_risk_decimal_boundaries(risk_text: str) -> None:
    request = PaperActivationHttpRequest.model_validate(
        {
            "activationRequestId": str(ACTIVATION_ID),
            "strategyVersionId": str(VERSION_ID),
            "parameters": {},
            "riskPerTrade": risk_text,
            "confirmation": "ACTIVATE_PAPER",
        }
    )
    activation = PaperActivationRequest(
        activation_request_id=ACTIVATION_ID,
        strategy_version_id=VERSION_ID,
        parameters={},
        risk_per_trade=request.risk_per_trade,
        confirmation="ACTIVATE_PAPER",
    )

    assert request.risk_per_trade == Decimal(risk_text)
    assert activation.risk_per_trade == Decimal(risk_text)
    serialized = request.model_dump(by_alias=True, mode="json")["riskPerTrade"]
    assert isinstance(serialized, str)
    assert Decimal(serialized) == Decimal(risk_text)
