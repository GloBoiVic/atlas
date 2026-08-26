"""Public V2 HTTP contract.

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


class ExperimentStrategyVersionOptionResponse(StrictModel):
    id: UUID
    strategy_key: str
    name: str
    version: int
    display_name: str
    created_at: str
    implementation_key: str
    source_fingerprint: str
    parameter_schema: list[dict[str, Any]]
    required_historical_context_bars: int
    architecture: str
    execution_available: bool
    unavailable_reason: str | None


class ExperimentDatasetSnapshotOptionResponse(StrictModel):
    id: UUID
    fingerprint: str
    coverage_start: str
    coverage_end: str
    snapshot_schema: str
    integrity: dict[str, Any]


class ExperimentConfigurationOptionsResponse(StrictModel):
    strategy_versions: list[ExperimentStrategyVersionOptionResponse]
    dataset_snapshots: list[ExperimentDatasetSnapshotOptionResponse]
    defaults: dict[str, Any]
    simulation_assumptions: dict[str, Any]


class ErrorBody(BaseModel):
    model_config = ConfigDict(
        alias_generator=_camel, populate_by_name=True, extra="forbid"
    )

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class PriceAnalysisBarResponse(StrictModel):
    t: str
    o: str
    h: str
    l: str  # noqa: E741 - public OHLC contract uses the canonical short key
    c: str


class PriceAnalysisEmaResponse(StrictModel):
    t: str
    v: str


class PriceAnalysisWindowResponse(StrictModel):
    start: str
    end: str


class PriceAnalysisPointResponse(StrictModel):
    t: str
    price: str


class PriceAnalysisRangeResponse(StrictModel):
    price: str
    from_: str = Field(alias="from")
    to: str


class PriceAnalysisTradeResponse(StrictModel):
    sequence: int
    direction: str
    entry: PriceAnalysisPointResponse
    exit: PriceAnalysisPointResponse | None
    stop: PriceAnalysisRangeResponse | None
    target: PriceAnalysisRangeResponse | None


class PriceAnalysisFactResponse(StrictModel):
    trade_sequence: int
    reference: dict[str, str]
    sweep: dict[str, str]
    confirmation: dict[str, str]
    trend_relation: str | None = None
    atr: str | None = None
    stop_price: str | None = None
    trigger_price: str | None = None


class PriceAnalysisEvidenceResponse(StrictModel):
    trade_sequence: int
    setup: dict[str, Any]


class PriceAnalysisLandmarkResponse(StrictModel):
    kind: str
    trade_sequence: int
    time: str
    high: str | None = None
    low: str | None = None
    price: str | None = None
    basis: str | None = None


class ProposalStatusResponse(StrictModel):
    trade_sequence: int
    entry_policy: str | None = None
    trigger_price: str | None = None
    trigger_price_basis: str | None = None
    expiry: str | None = None
    expiry_bars: int | None = None
    proposal_status: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class PriceAnalysisDiagnosticsResponse(StrictModel):
    truncated: bool
    ema_period: int
    required_historical_context_bars: int
    snapshot_fingerprint: str
    m15_eligible_count: int
    m15_returned_count: int
    trade_eligible_count: int
    trade_returned_count: int
    omitted_range: dict[str, str] | None
    omitted_m15_count: int
    omitted_trade_count: int


class PriceAnalysisResponse(StrictModel):
    m15: list[PriceAnalysisBarResponse]
    ema: list[PriceAnalysisEmaResponse]
    trading_window: PriceAnalysisWindowResponse
    trades: list[PriceAnalysisTradeResponse]
    reference: list[PriceAnalysisFactResponse]
    diagnostics: PriceAnalysisDiagnosticsResponse
    provenance: dict[str, Any] = Field(default_factory=dict)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    landmarks: list[PriceAnalysisLandmarkResponse] = Field(default_factory=list)
    proposal_diagnostics: list[ProposalStatusResponse] = Field(default_factory=list)
    setup_facts: list[dict[str, Any]] = Field(default_factory=list)


class HistoricalDataLoadRequest(StrictModel):
    strategy_version_id: UUID
    trading_start: datetime
    trading_end: datetime


class HistoricalDataLoadStatusResponse(StrictModel):
    id: UUID
    display_label: str
    status: str
    status_url: str
    source: dict[str, Any]
    requested_period: dict[str, str]
    load_range: dict[str, str]
    progress: dict[str, Any]
    coverage: dict[str, Any] | None
    snapshot: dict[str, Any] | None
    experiment_validation: dict[str, Any] | None
    failure: dict[str, Any] | None
    created_at: str
    started_at: str | None
    finished_at: str | None


class HistoricalDataCapabilityResponse(StrictModel):
    provider: str
    instrument: str
    resolution: str
    components: list[str]
    available: bool
    reason_code: str | None


class ApiResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    # The concrete payload is represented by route-specific OpenAPI schemas
    # where useful; this base makes the envelope stable for injected services.
    pass


class StrategyLatestVersionResponse(StrictModel):
    id: UUID
    version_number: int
    display_name: str


class StrategyCatalogItemResponse(StrictModel):
    strategy_key: str
    name: str
    description: str
    latest_version: StrategyLatestVersionResponse | None
    version_count: int
    experiment_count: int
    last_experiment_at: datetime | None


class StrategyCatalogResponse(StrictModel):
    items: list[StrategyCatalogItemResponse]


class StrategySourceManifestItem(StrictModel):
    relative_path: str
    byte_length: int


class StrategyVersionHistoryResponse(StrictModel):
    id: UUID
    display_name: str
    version_number: int
    implementation_key: str
    source_fingerprint: str
    created_at: datetime
    git_sha: str | None
    source_manifest: list[StrategySourceManifestItem]
    parameter_schema: list[dict[str, Any]]
    context_timeframes: list[str]
    timeframe: str
    required_historical_context_bars: int
    state_schema_version: int
    capabilities: list[str]
    experiment_count: int
    last_used_at: datetime | None
    execution_available: bool
    unavailable_reason: str | None
    market_requirements: dict[str, Any]
    methodology: dict[str, Any]


class StrategyDetailResponse(StrictModel):
    strategy_key: str
    name: str
    description: str
    version_count: int
    experiment_count: int
    last_experiment_at: datetime | None
    versions: list[StrategyVersionHistoryResponse]


class ExperimentIdentityStrategyVersion(StrictModel):
    id: UUID | None
    display_name: str | None
    key: str | None
    version: int | None


class ExperimentIdentityInstrument(StrictModel):
    code: str | None
    base_currency: str | None
    quote_currency: str | None


class ExperimentIdentityAnalytical(StrictModel):
    resolution: str | None
    price_component: str | None


class ExperimentIdentityProvider(StrictModel):
    name: str | None
    symbol: str | None


class ExperimentIdentityPeriod(StrictModel):
    start: str
    end: str


class ExperimentIdentity(StrictModel):
    strategy_version: ExperimentIdentityStrategyVersion | None
    instrument: ExperimentIdentityInstrument | None
    analytical: ExperimentIdentityAnalytical
    provider: ExperimentIdentityProvider | None
    trading_period: ExperimentIdentityPeriod


class ExperimentReadResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    identity: ExperimentIdentity


class ExperimentListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[ExperimentReadResponse]
    next_cursor: str | None = None


class ComparisonWarningResponse(StrictModel):
    code: str
    severity: str
    explanation: str
    paths: list[str]


class ComparisonDifferenceResponse(StrictModel):
    path: str
    values: dict[str, Any]


class ComparisonExperimentResponse(StrictModel):
    slot: str
    id: UUID
    label: str
    strategy: dict[str, Any]
    instrument: dict[str, Any]
    dataset_snapshot: dict[str, Any]
    trading_period: dict[str, Any]
    parameters: dict[str, Any]
    starting_capital: dict[str, Any]
    risk: dict[str, Any]
    simulation: dict[str, Any]
    model_version: str
    metric_contract: dict[str, Any]
    metrics: dict[str, Any]


class ExperimentComparisonResponse(StrictModel):
    experiments: list[ComparisonExperimentResponse]
    differences: list[ComparisonDifferenceResponse]
    warnings: list[ComparisonWarningResponse]
    changed_parameter_keys: list[str]
    strong_parameter_isolation: bool
