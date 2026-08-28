"""Canonical streaming fingerprints for immutable dataset snapshots."""

import hashlib
import json
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from backend.domain.market_data import (
    FINGERPRINT_SCHEMA,
    FINGERPRINT_SCHEMA_V2,
    Bar,
    PriceComponent,
    VenueInstrument,
)


def canonical_decimal(value: Decimal) -> str:
    if type(value) is not Decimal or value.is_nan() or value.is_infinite():
        raise ValueError("fingerprint values must be finite Decimal values")
    if value == 0:
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def canonical_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0) or value.microsecond:
        raise ValueError("fingerprint timestamps must be second-precision UTC")
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_value(value: Any) -> Any:
    """Convert nested timestamp values to the one V2 wire representation."""
    if isinstance(value, datetime):
        return canonical_timestamp(value)
    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


def _line(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            _canonical_value(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("utf-8")


def canonical_jsonl(
    venue_instrument: VenueInstrument,
    coverage_start: datetime,
    coverage_end: datetime,
    components: tuple[PriceComponent | str, ...],
    bars: Iterable[Bar],
    *,
    session_policy: str,
    alignment_convention: str,
) -> Iterator[bytes]:
    component_values: tuple[str, ...] = tuple(
        component.value if isinstance(component, PriceComponent) else component
        for component in components
    )
    yield _line(
        {
            "alignment_convention": alignment_convention,
            "base_resolution": "1m",
            "components": list(component_values),
            "coverage_end": canonical_timestamp(coverage_end),
            "coverage_start": canonical_timestamp(coverage_start),
            "instrument": venue_instrument.instrument.value,
            "provider": venue_instrument.provider.value,
            "provider_symbol": venue_instrument.provider_symbol,
            "schema": FINGERPRINT_SCHEMA,
            "session_policy": session_policy,
        }
    )
    ordered = sorted(bars, key=lambda bar: (bar.start_time, bar.price_component.value))
    for bar in ordered:
        yield _line(
            {
                "complete": True,
                "price_component": bar.price_component.value,
                "end_time": canonical_timestamp(bar.end_time),
                "high": canonical_decimal(bar.high),
                "low": canonical_decimal(bar.low),
                "open": canonical_decimal(bar.open),
                "close": canonical_decimal(bar.close),
                "start_time": canonical_timestamp(bar.start_time),
                "volume": None if bar.volume is None else canonical_decimal(bar.volume),
            }
        )


def dataset_fingerprint(
    venue_instrument: VenueInstrument,
    coverage_start: datetime,
    coverage_end: datetime,
    components: tuple[PriceComponent | str, ...],
    bars: Iterable[Bar],
    *,
    session_policy: str,
    alignment_convention: str,
) -> str:
    digest = hashlib.sha256()
    for chunk in canonical_jsonl(
        venue_instrument,
        coverage_start,
        coverage_end,
        components,
        bars,
        session_policy=session_policy,
        alignment_convention=alignment_convention,
    ):
        digest.update(chunk)
    return digest.hexdigest()


def dataset_fingerprint_v2(
    *,
    metadata: dict[str, Any],
    analytical_members: Iterable[dict[str, Any]],
    execution_members: Iterable[dict[str, Any]],
    gaps: Iterable[dict[str, Any]],
) -> str:
    """Hash the exact V2 contract, without imposing acquisition semantics."""
    digest = hashlib.sha256()
    header = dict(metadata)
    header["schema"] = FINGERPRINT_SCHEMA_V2
    for kind, values in (
        ("header", (header,)),
        ("analytical", analytical_members),
        ("execution", execution_members),
        ("gap", gaps),
    ):
        for value in values:
            digest.update(_line({"kind": kind, "value": value}))
    return digest.hexdigest()


class V2FingerprintBuilder:
    """Incremental V2 hasher; callers may feed database rows in bounded batches."""

    def __init__(self, metadata: dict[str, Any]) -> None:
        self._digest = hashlib.sha256()
        header = dict(metadata)
        header["schema"] = FINGERPRINT_SCHEMA_V2
        self._digest.update(_line({"kind": "header", "value": header}))

    def add(self, kind: str, value: dict[str, Any]) -> None:
        if kind not in {"analytical", "execution", "gap"}:
            raise ValueError("invalid V2 fingerprint section")
        self._digest.update(_line({"kind": kind, "value": value}))

    def hexdigest(self) -> str:
        return self._digest.hexdigest()


def bar_content_fingerprint(bar: Bar) -> str:
    """Stable provider-observation fingerprint shared by V2 memberships."""
    value = {"bar": bar.to_json(), "content_schema": "ATLAS_BAR_CONTENT_SHA256_V1"}
    return hashlib.sha256(_line(value)).hexdigest()


fingerprint_dataset = dataset_fingerprint

__all__ = [
    "canonical_decimal",
    "canonical_jsonl",
    "canonical_timestamp",
    "dataset_fingerprint",
    "fingerprint_dataset",
    "dataset_fingerprint_v2",
    "bar_content_fingerprint",
]
