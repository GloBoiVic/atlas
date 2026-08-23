"""Public Phase 5 HTTP contract.

The API deliberately keeps the financial representation as decimal strings and
rejects unknown request fields.  Response payloads use small typed envelopes;
the domain read services remain the authority for their contents.
"""

# Contract declarations are intentionally kept one field per line where the
# generated OpenAPI names remain easy to audit.
# ruff: noqa: E501

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(item.title() for item in tail)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel, populate_by_name=True, extra="forbid"
    )


class PeriodRequest(StrictModel):
    strategy_version_id: UUID
    dataset_snapshot_id: UUID
    trading_start: datetime
    trading_end: datetime


class ExperimentCreateRequest(PeriodRequest):
    starting_capital: Decimal = Field(gt=0)
    risk_per_trade: Decimal = Field(gt=0, lt=1)
    parameters: dict[str, Any]
    slippage_ticks: int = Field(ge=0)
    commission_per_unit: Decimal = Field(ge=0)

    @field_serializer("starting_capital", "risk_per_trade", "commission_per_unit")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class ErrorBody(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True, extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    # The concrete payload is represented by route-specific OpenAPI schemas
    # where useful; this base makes the envelope stable for injected services.
    pass
