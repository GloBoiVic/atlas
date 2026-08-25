"""Versioned result and metric-state vocabulary contracts."""

from typing import Final, Literal

MetricState = Literal["VALUE", "INFINITE", "UNAVAILABLE", "LEGACY_UNCOMPUTED"]

LEGACY_METRIC_SCHEMA_VERSION: Final = "LEGACY_UNCOMPUTED"
PHASE5_RESULT_SCHEMA_VERSION: Final = "PHASE5_EXPERIMENT_RESULT_V2"
PHASE5_METRIC_SCHEMA_VERSION: Final = "PHASE5_METRICS_V1"

METRIC_STATE_KEYS: Final[tuple[str, ...]] = (
    "sharpe_ratio",
    "profit_factor",
    "win_rate",
    "expectancy_net_pnl",
)

LEGACY_METRIC_STATES: Final[dict[str, str]] = {
    key: LEGACY_METRIC_SCHEMA_VERSION for key in METRIC_STATE_KEYS
}

# Stable, calculation-free fixtures used by the metrics implementation and tests.
METRIC_STATE_FIXTURES: Final[dict[str, dict[str, object]]] = {
    "finite": {key: "VALUE" for key in METRIC_STATE_KEYS},
    "infinite_profit_factor": {
        **{key: "VALUE" for key in METRIC_STATE_KEYS},
        "profit_factor": "INFINITE",
    },
    "empty": {key: "UNAVAILABLE" for key in METRIC_STATE_KEYS},
}
