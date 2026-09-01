"""Read-only, provider-specific OANDA Practice EUR/USD pricing observations."""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from backend.config import Settings

from .account import OandaPracticeAccountIdentity, bind_oanda_practice_account
from .primitives import OandaPrimitiveError, parse_decimal
from .request import OandaObservationRequester, validate_token
from .source import OandaNormalizationError

_PRICING_PATH = "/v3/accounts/{account_id}/pricing"
_REQUEST_ERROR_SUBJECT = "pricing"
_PROVIDER_INSTRUMENT = "EUR_USD"
_RFC3339_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:"
    r"[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})"
)


class OandaPricingNormalizationError(OandaNormalizationError):
    """An OANDA pricing observation could not become a safe observation."""


def _timestamp(value: Any) -> datetime:
    if type(value) is not str or _RFC3339_PATTERN.fullmatch(value) is None:
        raise OandaPricingNormalizationError("OANDA pricing Price has invalid time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise OandaPricingNormalizationError(
            "OANDA pricing Price has invalid time"
        ) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OandaPricingNormalizationError(
            "OANDA pricing Price time is not timezone-aware"
        )
    return parsed.astimezone(UTC)


def _price(value: Any) -> Decimal:
    try:
        result = parse_decimal(value)
    except OandaPrimitiveError:
        raise OandaPricingNormalizationError(
            "OANDA pricing bucket has invalid price"
        ) from None
    if result <= 0:
        raise OandaPricingNormalizationError("OANDA pricing bucket has invalid price")
    return result


def _liquidity(value: Any) -> Decimal:
    if type(value) not in (int, float):
        raise OandaPricingNormalizationError(
            "OANDA pricing bucket has invalid liquidity"
        )
    if type(value) is float and not math.isfinite(value):
        raise OandaPricingNormalizationError(
            "OANDA pricing bucket has invalid liquidity"
        )
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise OandaPricingNormalizationError(
            "OANDA pricing bucket has invalid liquidity"
        ) from None
    if not result.is_finite() or result < 0:
        raise OandaPricingNormalizationError(
            "OANDA pricing bucket has invalid liquidity"
        )
    return result


def _normalized_decimal(value: Any, name: str, *, positive: bool = False) -> Decimal:
    if type(value) is not Decimal or not value.is_finite() or (positive and value <= 0):
        raise OandaPricingNormalizationError(f"OANDA pricing bucket has invalid {name}")
    return value


@dataclass(frozen=True, slots=True)
class OandaPracticePriceBucket:
    """One provider-observed OANDA price/liquidity bucket."""

    price: Decimal
    liquidity: Decimal

    def __post_init__(self) -> None:
        _normalized_decimal(self.price, "price", positive=True)
        _normalized_decimal(self.liquidity, "liquidity")
        if self.liquidity < 0:
            raise OandaPricingNormalizationError(
                "OANDA pricing bucket has invalid liquidity"
            )


@dataclass(frozen=True, slots=True)
class OandaPracticeEurUsdPricingObservation:
    """The retained provider facts from one EUR/USD pricing response."""

    identity: OandaPracticeAccountIdentity
    provider_instrument: Literal["EUR_USD"]
    price_time: datetime
    tradeable: bool
    bids: tuple[OandaPracticePriceBucket, ...]
    asks: tuple[OandaPracticePriceBucket, ...]

    def __post_init__(self) -> None:
        if type(self.identity) is not OandaPracticeAccountIdentity:
            raise OandaPricingNormalizationError(
                "OANDA pricing observation has an invalid identity"
            )
        if type(self.provider_instrument) is not str or (
            self.provider_instrument != _PROVIDER_INSTRUMENT
        ):
            raise OandaPricingNormalizationError(
                "OANDA pricing observation has an invalid instrument"
            )
        if type(self.price_time) is not datetime:
            raise OandaPricingNormalizationError(
                "OANDA pricing observation has invalid price_time"
            )
        if self.price_time.tzinfo is None or self.price_time.utcoffset() is None:
            raise OandaPricingNormalizationError(
                "OANDA pricing observation price_time is not timezone-aware"
            )
        object.__setattr__(self, "price_time", self.price_time.astimezone(UTC))
        if type(self.tradeable) is not bool:
            raise OandaPricingNormalizationError(
                "OANDA pricing observation has invalid tradeable"
            )
        if type(self.bids) is not tuple or any(
            type(bucket) is not OandaPracticePriceBucket for bucket in self.bids
        ):
            raise OandaPricingNormalizationError(
                "OANDA pricing observation has invalid bids"
            )
        if type(self.asks) is not tuple or any(
            type(bucket) is not OandaPracticePriceBucket for bucket in self.asks
        ):
            raise OandaPricingNormalizationError(
                "OANDA pricing observation has invalid asks"
            )


class OandaPracticeEurUsdPricingReader:
    """Read EUR/USD pricing for an already validated Practice identity."""

    def __init__(
        self,
        token: SecretStr | None,
        identity: OandaPracticeAccountIdentity,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 20.0,
    ) -> None:
        self._requester = OandaObservationRequester(
            token,
            client=client,
            transport=transport,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
        )
        if type(identity) is not OandaPracticeAccountIdentity:
            raise OandaPricingNormalizationError(
                "OANDA pricing reader requires a validated account identity"
            )
        self._token = token
        self._identity = identity

    def read(self) -> OandaPracticeEurUsdPricingObservation:
        """Read and normalize one immutable EUR/USD pricing observation."""
        payload = self._read_payload()
        return self._normalize_observation(payload)

    def _read_payload(self) -> Mapping[str, Any]:
        self._validate_configuration()
        path = _PRICING_PATH.format(
            account_id=quote(self._identity.provider_account_id, safe="-")
        )
        payload = self._requester.get_json(
            path,
            error_subject=_REQUEST_ERROR_SUBJECT,
            params={"instruments": _PROVIDER_INSTRUMENT},
        )
        if not isinstance(payload, dict):
            raise OandaPricingNormalizationError(
                "OANDA pricing response is not an object"
            )
        return cast(Mapping[str, Any], payload)

    def _validate_configuration(self) -> None:
        validate_token(self._token)

    def _normalize_observation(
        self, payload: Mapping[str, Any]
    ) -> OandaPracticeEurUsdPricingObservation:
        prices_value = payload.get("prices")
        if not isinstance(prices_value, list):
            raise OandaPricingNormalizationError(
                "OANDA pricing response must contain exactly one Price"
            )
        raw_prices = cast(list[Any], prices_value)
        if len(raw_prices) != 1:
            raise OandaPricingNormalizationError(
                "OANDA pricing response must contain exactly one Price"
            )
        price_value = raw_prices[0]
        if not isinstance(price_value, dict):
            raise OandaPricingNormalizationError(
                "OANDA pricing response has an invalid Price"
            )
        price = cast(dict[str, Any], price_value)
        if type(price.get("instrument")) is not str or (
            price["instrument"] != _PROVIDER_INSTRUMENT
        ):
            raise OandaPricingNormalizationError(
                "OANDA pricing Price has an invalid instrument"
            )

        bids = self._normalize_buckets(price, "bids")
        asks = self._normalize_buckets(price, "asks")
        tradeable = price.get("tradeable")
        if type(tradeable) is not bool:
            raise OandaPricingNormalizationError(
                "OANDA pricing Price has invalid tradeable"
            )
        return OandaPracticeEurUsdPricingObservation(
            identity=self._identity,
            provider_instrument=_PROVIDER_INSTRUMENT,
            price_time=_timestamp(price.get("time")),
            tradeable=tradeable,
            bids=bids,
            asks=asks,
        )

    @staticmethod
    def _normalize_buckets(
        price: Mapping[str, Any], side: Literal["bids", "asks"]
    ) -> tuple[OandaPracticePriceBucket, ...]:
        buckets_value = price.get(side)
        if not isinstance(buckets_value, list):
            raise OandaPricingNormalizationError(
                f"OANDA pricing Price has invalid {side}"
            )
        raw_buckets = cast(list[Any], buckets_value)
        buckets: list[OandaPracticePriceBucket] = []
        for bucket_value in raw_buckets:
            if not isinstance(bucket_value, dict):
                raise OandaPricingNormalizationError(
                    f"OANDA pricing {side} has an invalid bucket"
                )
            bucket = cast(dict[str, Any], bucket_value)
            buckets.append(
                OandaPracticePriceBucket(
                    price=_price(bucket.get("price")),
                    liquidity=_liquidity(bucket.get("liquidity")),
                )
            )
        return tuple(buckets)


def read_oanda_practice_eur_usd_pricing(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> OandaPracticeEurUsdPricingObservation:
    """Validate settings' account, then read its independent EUR/USD pricing."""
    identity = bind_oanda_practice_account(
        settings,
        client=client,
        transport=transport,
    )
    return OandaPracticeEurUsdPricingReader(
        settings.oanda_api_token,
        identity,
        client=client,
        transport=transport,
        connect_timeout_seconds=settings.oanda_connect_timeout_seconds,
        read_timeout_seconds=settings.oanda_read_timeout_seconds,
    ).read()


__all__ = [
    "OandaPracticeEurUsdPricingObservation",
    "OandaPracticeEurUsdPricingReader",
    "OandaPracticePriceBucket",
    "OandaPricingNormalizationError",
    "read_oanda_practice_eur_usd_pricing",
]
