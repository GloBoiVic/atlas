"""ATLAS_DATASET_SHA256_V1 canonical streaming fingerprint."""

import hashlib
import json
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from backend.domain.market_data import (
    FINGERPRINT_SCHEMA,
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


def _line(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
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


fingerprint_dataset = dataset_fingerprint

__all__ = [
    "canonical_decimal",
    "canonical_jsonl",
    "canonical_timestamp",
    "dataset_fingerprint",
    "fingerprint_dataset",
]
