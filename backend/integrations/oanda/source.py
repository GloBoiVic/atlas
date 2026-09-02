"""Synchronous, read-only OANDA Practice historical candle source.

Only canonical ``Bar`` values and sanitized diagnostics leave this module.  The
provider's response shape is deliberately kept private to the request method.
"""

import math
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from time import sleep
from typing import Any, Protocol, cast

import httpx
from pydantic import SecretStr

from backend.domain.market_data import (
    Bar,
    InputError,
    Instrument,
    PriceComponent,
    Timeframe,
)
from backend.market_data.session_policy import EXPECTED_DATA, OANDA_EUR_USD_POLICY

OANDA_PRACTICE_BASE_URL = "https://api-fxpractice.oanda.com"
_M1_WINDOW_MINUTES = 4_000
_M15_WINDOW_MINUTES = 60_000
_MAX_ATTEMPTS = 3
_RETRY_AFTER_CAP_SECONDS = 30.0
_BACKOFF_SECONDS = (0.25, 0.5)


class OandaError(RuntimeError):
    """Base for sanitized, actionable OANDA source failures."""


class OandaConfigurationError(OandaError):
    """The source cannot make a safe request with its configuration."""


class OandaNormalizationError(OandaError):
    """A complete provider candle could not become a canonical bar group."""


class OandaRequestError(OandaError):
    """A provider request failed; no provider response body is retained."""

    def __init__(
        self,
        status_code: int | None,
        attempts: int,
        message: str,
        *,
        request_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.attempts = attempts
        self.request_id = request_id
        super().__init__(message)


class OandaAuthError(OandaRequestError):
    """OANDA rejected the credential or authorization."""


@dataclass(frozen=True, slots=True)
class IncompleteCandle:
    start_time: datetime
    reason: str = "provider candle is not complete"


@dataclass(frozen=True, slots=True)
class RequestDiagnostic:
    start: datetime
    end: datetime
    attempts: int
    status_code: int | None


@dataclass(frozen=True, slots=True)
class FetchDiagnostics:
    requests: tuple[RequestDiagnostic, ...]

    @property
    def attempts(self) -> int:
        return sum(request.attempts for request in self.requests)


@dataclass(frozen=True, slots=True)
class FetchResult:
    bars: tuple[Bar, ...]
    incomplete: tuple[IncompleteCandle, ...]
    diagnostics: FetchDiagnostics


class HistoricalBarSource(Protocol):
    def fetch(self, start: datetime, end: datetime) -> FetchResult: ...


def _rfc3339(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("historical range must be timezone-aware UTC")
    if value.second or value.microsecond:
        raise ValueError("historical range must be minute-aligned")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _windows(
    start: datetime, end: datetime, *, window_minutes: int
) -> Iterator[tuple[datetime, datetime]]:
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(minutes=window_minutes), end)
        yield cursor, window_end
        cursor = window_end


def _retry_after(response: httpx.Response) -> float:
    value = response.headers.get("Retry-After")
    if value is None:
        return 0.0
    try:
        seconds = float(value)
    except ValueError:
        seconds = -1.0
    if math.isfinite(seconds) and seconds >= 0:
        return min(seconds, _RETRY_AFTER_CAP_SECONDS)
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            return 0.0
        seconds = (retry_at.astimezone(UTC) - datetime.now(UTC)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not math.isfinite(seconds) or seconds < 0:
        return 0.0
    return min(seconds, _RETRY_AFTER_CAP_SECONDS)


def _decimal(value: Any, name: str) -> Decimal:
    if not isinstance(value, str):
        raise OandaNormalizationError(f"complete candle has invalid {name}")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise OandaNormalizationError(f"complete candle has invalid {name}") from None
    if result.is_nan() or result.is_infinite():
        raise OandaNormalizationError(f"complete candle has invalid {name}")
    return result


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise OandaNormalizationError("complete candle has invalid time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise OandaNormalizationError("complete candle has invalid time") from None
    if parsed.tzinfo is None:
        raise OandaNormalizationError("complete candle time is not timezone-aware")
    return parsed.astimezone(UTC)


def _group(
    candle: dict[str, Any],
    start: datetime,
    timeframe: Timeframe,
    components: tuple[tuple[PriceComponent, str], ...],
) -> tuple[Bar, ...]:
    result: list[Bar] = []
    for component, key in components:
        prices = candle.get(key)
        if not isinstance(prices, dict):
            raise OandaNormalizationError(
                "complete candle is missing a price component"
            )
        try:
            values = tuple(
                _decimal(prices[field], field) for field in ("o", "h", "l", "c")
            )
            bar = Bar(
                Instrument.EUR_USD,
                timeframe,
                component,
                start,
                start + timedelta(minutes=1 if timeframe is Timeframe.M1 else 15),
                values[0],
                values[1],
                values[2],
                values[3],
                volume=Decimal(str(candle["volume"])) if "volume" in candle else None,
            )
        except (KeyError, TypeError, InputError, InvalidOperation) as error:
            raise OandaNormalizationError(
                "complete candle contains invalid market data"
            ) from error
        result.append(bar)
    return tuple(result)


class OandaHistoricalBarSource:
    """Fetch EUR/USD M1 MID/BID/ASK candles from the Practice REST endpoint."""

    def __init__(
        self,
        token: SecretStr | None,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 20.0,
    ) -> None:
        if not (0 < connect_timeout_seconds <= 30) or not (
            0 < read_timeout_seconds <= 120
        ):
            raise OandaConfigurationError("OANDA timeouts are outside bounded limits")
        self._token = token
        self._client = client
        self._transport = transport
        self._timeout = httpx.Timeout(
            read=read_timeout_seconds,
            connect=connect_timeout_seconds,
            write=connect_timeout_seconds,
            pool=connect_timeout_seconds,
        )

    def fetch(self, start: datetime, end: datetime) -> FetchResult:
        return self._fetch(
            start,
            end,
            granularity="M1",
            price="MBA",
            timeframe=Timeframe.M1,
            components=(
                (PriceComponent.MID, "mid"),
                (PriceComponent.BID, "bid"),
                (PriceComponent.ASK, "ask"),
            ),
        )

    def fetch_native_m15(self, start: datetime, end: datetime) -> FetchResult:
        """Fetch the immutable provider-native analytical M15 MID series."""
        return self._fetch(
            start,
            end,
            granularity="M15",
            price="M",
            timeframe=Timeframe.M15,
            components=((PriceComponent.MID, "mid"),),
            validate_m15_alignment=True,
        )

    # Explicit spelling for callers that want the contract name in code.
    fetch_m15_native = fetch_native_m15

    def fetch_execution_m1(self, start: datetime, end: datetime) -> FetchResult:
        """Fetch sparse completed M1 BID/ASK observations for execution."""
        return self._fetch(
            start,
            end,
            granularity="M1",
            price="BA",
            timeframe=Timeframe.M1,
            components=((PriceComponent.BID, "bid"), (PriceComponent.ASK, "ask")),
            omit_unavailable_m1=True,
        )

    def _fetch(
        self,
        start: datetime,
        end: datetime,
        *,
        granularity: str,
        price: str,
        timeframe: Timeframe,
        components: tuple[tuple[PriceComponent, str], ...],
        validate_m15_alignment: bool = False,
        omit_unavailable_m1: bool = False,
    ) -> FetchResult:
        _rfc3339(start)
        _rfc3339(end)
        if end <= start:
            raise ValueError("historical range must be positive")
        if self._token is None or not self._token.get_secret_value():
            raise OandaConfigurationError("OANDA API token is required")
        diagnostics: list[RequestDiagnostic] = []
        provider_candles: dict[datetime, dict[str, Any]] = {}
        owned_client = self._client is None
        client = self._client or httpx.Client(
            transport=self._transport,
            timeout=self._timeout,
            base_url=OANDA_PRACTICE_BASE_URL,
            trust_env=False,
        )
        try:
            window_minutes = (
                _M15_WINDOW_MINUTES
                if timeframe is Timeframe.M15
                else _M1_WINDOW_MINUTES
            )
            for window_start, window_end in _windows(
                start, end, window_minutes=window_minutes
            ):
                candles, diagnostic = self._request(
                    client,
                    window_start,
                    window_end,
                    granularity=granularity,
                    price=price,
                )
                diagnostics.append(diagnostic)
                for candle in candles:
                    candle_time = _timestamp(candle.get("time"))
                    if not (window_start <= candle_time < window_end):
                        continue
                    if candle_time.second or candle_time.microsecond:
                        raise OandaNormalizationError(
                            "provider candle is not UTC minute aligned"
                        )
                    if validate_m15_alignment and candle_time.minute % 15:
                        raise OandaNormalizationError(
                            "native M15 candle is not UTC quarter-hour aligned"
                        )
                    prior = provider_candles.get(candle_time)
                    if prior is not None and prior != candle:
                        raise OandaNormalizationError("conflicting duplicate candle")
                    provider_candles[candle_time] = candle
        finally:
            if owned_client:
                client.close()
        normalized: list[Bar] = []
        incomplete: list[IncompleteCandle] = []
        for candle_time in sorted(provider_candles):
            candle = provider_candles[candle_time]
            # OANDA can return the last/first boundary candle around its
            # maintenance interval in a larger calendar request.  Those
            # observations are not canonical execution data under the frozen
            # session policy.  Filter them only after timestamp and duplicate
            # validation; native M15 remains untouched and malformed provider
            # candles still fail through _group.
            expected_session = (
                not omit_unavailable_m1
                or timeframe is not Timeframe.M1
                or OANDA_EUR_USD_POLICY.classify_minute(candle_time)[0] == EXPECTED_DATA
            )
            if candle.get("complete") is True:
                bars = _group(candle, candle_time, timeframe, components)
                if expected_session:
                    normalized.extend(bars)
            elif expected_session:
                incomplete.append(IncompleteCandle(candle_time))
        return FetchResult(
            bars=tuple(normalized),
            incomplete=tuple(incomplete),
            diagnostics=FetchDiagnostics(tuple(diagnostics)),
        )

    def _request(
        self,
        client: httpx.Client,
        start: datetime,
        end: datetime,
        *,
        granularity: str = "M1",
        price: str = "MBA",
    ) -> tuple[list[dict[str, Any]], RequestDiagnostic]:
        token = self._token
        if token is None:
            raise OandaConfigurationError("OANDA API token is required")
        headers = {
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Accept-Datetime-Format": "RFC3339",
        }
        params = {
            "from": _rfc3339(start),
            "to": _rfc3339(end),
            "price": price,
            "granularity": granularity,
            "smooth": "false",
        }
        attempts = 0
        while attempts < _MAX_ATTEMPTS:
            attempts += 1
            try:
                response = client.get(
                    f"{OANDA_PRACTICE_BASE_URL}/v3/instruments/EUR_USD/candles",
                    params=params,
                    headers=headers,
                    timeout=self._timeout,
                )
            except httpx.RequestError:
                if attempts == _MAX_ATTEMPTS:
                    raise OandaRequestError(
                        None, attempts, "OANDA request failed after retries"
                    ) from None
                sleep(_BACKOFF_SECONDS[attempts - 1])
                continue
            status = response.status_code
            diagnostic = RequestDiagnostic(start, end, attempts, status)
            if status == 401 or status == 403:
                raise OandaAuthError(status, attempts, "OANDA authorization failed")
            if status in (400, 404):
                raise OandaRequestError(status, attempts, "OANDA request was rejected")
            if status == 429 or 500 <= status <= 599:
                if attempts == _MAX_ATTEMPTS:
                    raise OandaRequestError(
                        status,
                        attempts,
                        "OANDA transient request failed after retries",
                    )
                delay = _retry_after(response)
                if delay <= 0 or not math.isfinite(delay):
                    delay = _BACKOFF_SECONDS[attempts - 1]
                sleep(delay)
                continue
            if status < 200 or status >= 300:
                raise OandaRequestError(status, attempts, "OANDA request failed")
            try:
                payload: Any = response.json()
            except ValueError:
                raise OandaRequestError(
                    status, attempts, "OANDA returned invalid JSON"
                ) from None
            payload_dict = (
                cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
            )
            candles_value: Any = payload_dict.get("candles")
            raw_candles = cast(list[Any], candles_value)
            if not isinstance(candles_value, list) or any(
                not isinstance(item, dict) for item in raw_candles
            ):
                raise OandaRequestError(
                    status, attempts, "OANDA returned an invalid candle response"
                )
            candles = cast(list[dict[str, Any]], candles_value)
            return candles, diagnostic
        raise AssertionError("retry loop exhausted unexpectedly")


# Short alias used by callers that name the abstraction rather than the provider.
OandaHistoricalSource = OandaHistoricalBarSource
