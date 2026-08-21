"""The deliberately small operator command line for historical market data."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy.exc import SQLAlchemyError

from backend.config import Settings
from backend.domain.market_data import PriceComponent
from backend.integrations.oanda.source import (
    OandaAuthError,
    OandaConfigurationError,
    OandaHistoricalBarSource,
    OandaNormalizationError,
    OandaRequestError,
)
from backend.persistence.database import create_database_engine, create_session_factory

from .ingestion import HistoricalBarSource, MarketDataService
from .session_calendar import required_warmup_range

_UUID_SAFE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}")
_FINGERPRINT = re.compile(r"[0-9a-f]{64}")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(token|password|secret|authorization)\s*[=:]\s*[^\s,;]+"
)


def _timestamp(value: str) -> datetime:
    """Parse only explicit UTC RFC3339 minute timestamps."""
    if value.endswith("Z"):
        candidate = value[:-1] + "+00:00"
    else:
        candidate = value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        raise argparse.ArgumentTypeError("timestamp must be RFC3339 UTC") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError("timestamp must include UTC (Z or +00:00)")
    if parsed.second or parsed.microsecond:
        raise argparse.ArgumentTypeError("timestamp must be minute-aligned")
    return parsed.astimezone(UTC)


def _fingerprint(value: str) -> str:
    if _FINGERPRINT.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(
            "snapshot fingerprint must be a lowercase 64-character SHA-256"
        )
    return value


def _range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    if args.end <= args.start:
        raise ValueError("range must be positive")
    return args.start, args.end


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas-data")
    sub = parser.add_subparsers(dest="command", required=True)

    def ranged(name: str) -> argparse.ArgumentParser:
        command = sub.add_parser(name)
        command.add_argument("--start", required=True, type=_timestamp)
        command.add_argument("--end", required=True, type=_timestamp)
        command.add_argument("--json", action="store_true", dest="as_json")
        return command

    ranged("load-missing")
    ranged("refresh")
    coverage = ranged("coverage")
    coverage.add_argument("--warm-up-bars", type=int, default=0)
    ranged("snapshot")
    derive = sub.add_parser("derive-m15")
    derive.add_argument("--snapshot-fingerprint", required=True, type=_fingerprint)
    derive.add_argument(
        "--component", required=True, choices=[c.value for c in PriceComponent]
    )
    derive.add_argument("--json", action="store_true", dest="as_json")
    return parser


class _NoFetchSource:
    def fetch(self, _start: datetime, _end: datetime) -> Any:
        raise RuntimeError("historical source is not available")


def _service(settings: Settings, *, needs_oanda: bool) -> tuple[MarketDataService, Any]:
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    source = (
        OandaHistoricalBarSource(
            settings.oanda_api_token if needs_oanda else None,
            connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
            read_timeout_seconds=settings.oanda_read_timeout_seconds,
        )
        if needs_oanda
        else _NoFetchSource()
    )
    return MarketDataService(factory, cast(HistoricalBarSource, source)), engine


def _summary(
    command: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    counts: dict[str, int] | None = None,
    gaps: int = 0,
    fingerprint: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "Instrument": "EUR/USD",
        "provider": "OANDA",
        "command": command,
        "range": None
        if start is None
        else {
            "start": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "end": end.isoformat(timespec="seconds").replace("+00:00", "Z")
            if end is not None
            else None,
        },
        "counts": counts or {},
        "gaps": gaps,
        "fingerprint": fingerprint,
    }
    if extra:
        result.update(extra)
    return result


def _emit(value: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
        return
    print(
        " ".join(
            f"{key}={json.dumps(value[key], sort_keys=True, separators=(',', ':'))}"
            for key in value
        )
    )


def _report(command: str, report: Any, as_json: bool) -> int:
    coverage = report.coverage
    gaps = _coverage_gaps(coverage)
    value = _summary(
        command,
        start=report.requested_start,
        end=report.requested_end,
        counts={
            "expected_open_minutes": coverage.expected_open_minutes,
            "expected_closure_minutes": coverage.expected_closure_minutes,
            "member_minutes": coverage.member_minutes,
            "inserted": getattr(report, "inserted", 0),
            "reactivated": getattr(report, "reactivated", 0),
            "unchanged": getattr(report, "unchanged", 0),
        },
        gaps=len(gaps),
        extra={
            "valid": coverage.valid,
            "gap_ranges": gaps,
            "closure_anomalies": [
                _format_timestamp(item) for item in coverage.closure_anomalies
            ],
            "unexpected_observations": [
                _format_timestamp(item) for item in coverage.unexpected_observations
            ],
            "incomplete_minutes": len(getattr(report, "incomplete_minutes", ())),
            "persisted": {
                "committed_ranges": [
                    _range_value(item[0], item[1])
                    for item in getattr(report, "committed_ranges", ())
                ],
                "inserted": getattr(report, "inserted", 0),
                "reactivated": getattr(report, "reactivated", 0),
                "unchanged": getattr(report, "unchanged", 0),
            },
            "snapshot_valid": None,
            "next_action": "continue; coverage is valid"
            if coverage.valid and getattr(report, "failure", None) is None
            else "repair reported gaps and retry",
        },
    )
    failure = getattr(report, "failure", None)
    if failure is not None:
        value["failed"] = {
            "classification": "historical_source_failure",
            "range": _range_value(report.failure.range_start, report.failure.range_end),
        }
    _emit(value, as_json)
    return 0 if getattr(report, "valid", coverage.valid) else 1


def _range_value(start: datetime, end: datetime) -> dict[str, str]:
    return {
        "start": _format_timestamp(start),
        "end": _format_timestamp(end),
    }


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _coverage_gaps(coverage: Any) -> list[dict[str, Any]]:
    return [
        {
            "start": _format_timestamp(gap.start),
            "end": _format_timestamp(gap.end),
            "components": [component.value for component in gap.components],
        }
        for gap in coverage.gaps
    ]


def _classification(error: BaseException) -> str:
    if isinstance(error, OandaAuthError):
        return "provider_authorization"
    if isinstance(error, OandaConfigurationError):
        return "provider_configuration"
    if isinstance(error, OandaNormalizationError):
        return "provider_data"
    if isinstance(error, OandaRequestError):
        return "provider_request"
    if isinstance(error, SQLAlchemyError):
        return "database"
    if isinstance(error, ValueError):
        return "validation"
    return "service_error"


def _redact_text(value: str) -> str:
    """Defence-in-depth redaction for diagnostics that are safe to retain."""
    value = _BEARER.sub("Bearer <redacted>", value)
    value = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=<redacted>", value)
    value = _UUID_SAFE.sub("<redacted-id>", value)
    return value


def _safe_error(error: BaseException) -> str:
    """Return only an allowlisted class, never exception text or DB details."""
    # Keep the redaction helper explicit for callers/tests handling controlled
    # diagnostics, but deliberately do not render arbitrary provider/DB text.
    _redact_text(str(error))
    return _classification(error)


def run(
    argv: Sequence[str] | None = None,
    *,
    service_factory: Callable[[bool], tuple[Any, Any]] | None = None,
) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        needs_oanda = args.command in {"load-missing", "refresh"}
        if args.command != "derive-m15":
            start, end = _range(args)
            if args.command == "coverage" and args.warm_up_bars < 0:
                raise ValueError("warm-up-bars must be non-negative")
        else:
            start = end = None
        if service_factory is not None:
            service, engine = service_factory(needs_oanda)
        else:
            settings = Settings()  # type: ignore[call-arg]
            service, engine = _service(settings, needs_oanda=needs_oanda)
        try:
            if args.command == "load-missing":
                assert start is not None and end is not None
                return _report(
                    args.command, service.load_missing(start, end), args.as_json
                )
            if args.command == "refresh":
                assert start is not None and end is not None
                return _report(
                    args.command, service.refresh_range(start, end), args.as_json
                )
            if args.command == "coverage":
                assert start is not None and end is not None
                coverage_start, _ = required_warmup_range(start, end, args.warm_up_bars)
                report = service.inspect_coverage(coverage_start, end)
                return _report(args.command, report, args.as_json)
            if args.command == "snapshot":
                assert start is not None and end is not None
                report = service.create_snapshot(start, end)
                value = _summary(
                    args.command,
                    start=start,
                    end=end,
                    counts={
                        "member_minutes": report.coverage.member_minutes,
                        "bar_count": report.snapshot.integrity_summary.get(
                            "bar_count", 0
                        )
                        if report.snapshot
                        else 0,
                    },
                    gaps=len(report.coverage.gaps),
                    fingerprint=report.snapshot.fingerprint
                    if report.snapshot
                    else None,
                    extra={
                        "valid": report.valid,
                        "snapshot_valid": report.valid,
                        "gap_ranges": _coverage_gaps(report.coverage),
                        "next_action": "continue; snapshot is valid"
                        if report.valid
                        else "repair reported gaps and retry",
                    },
                )
                if report.failure is not None:
                    value["failed"] = {"classification": "snapshot_integrity"}
                _emit(value, args.as_json)
                return 0 if report.valid else 1
            bars = service.derive_m15(
                args.snapshot_fingerprint, PriceComponent(args.component)
            )
            _emit(
                _summary(
                    args.command,
                    counts={"bars": len(bars)},
                    gaps=0,
                    fingerprint=args.snapshot_fingerprint,
                ),
                args.as_json,
            )
            return 0
        finally:
            engine.dispose()
    except Exception as error:
        print(
            json.dumps(
                {
                    "error": _safe_error(error),
                    "persisted": "unknown",
                    "coverage_valid": False,
                    "snapshot_valid": None,
                    "next_action": "inspect database/provider status and retry",
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            flush=True,
        )
        return 1
    except SystemExit:
        raise


def main() -> None:
    raise SystemExit(run())


__all__ = ["build_parser", "main", "run"]
