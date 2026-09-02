"""Pure executable-price candidates from normalized OANDA pricing facts."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from backend.domain.strategy import Direction

from .pricing import (
    OandaPracticeEurUsdPricingObservation,
    OandaPracticePriceBucket,
)
from .source import OandaError

OandaPricingSide = Literal["bids", "asks"]


class OandaPricingProjectionError(OandaError):
    """A normalized pricing observation cannot be projected safely."""


@dataclass(frozen=True, slots=True)
class OandaPracticeExecutablePriceCandidate:
    """One positive-liquidity, direction-appropriate provider candidate."""

    price: Decimal
    available_quantity: Decimal

    def __post_init__(self) -> None:
        if (
            type(self.price) is not Decimal
            or not self.price.is_finite()
            or self.price <= 0
        ):
            raise OandaPricingProjectionError(
                "OANDA executable-price candidate has invalid price"
            )
        if (
            type(self.available_quantity) is not Decimal
            or not self.available_quantity.is_finite()
            or self.available_quantity <= 0
        ):
            raise OandaPricingProjectionError(
                "OANDA executable-price candidate has invalid quantity"
            )


@dataclass(frozen=True, slots=True)
class OandaPricingBucketEvidence:
    """One required-side source bucket and its candidate disposition."""

    source_bucket: OandaPracticePriceBucket
    candidate: OandaPracticeExecutablePriceCandidate | None

    def __post_init__(self) -> None:
        if type(self.source_bucket) is not OandaPracticePriceBucket:
            raise OandaPricingProjectionError(
                "OANDA pricing evidence has an invalid source bucket"
            )
        if self.candidate is not None:
            if type(self.candidate) is not OandaPracticeExecutablePriceCandidate:
                raise OandaPricingProjectionError(
                    "OANDA pricing evidence has an invalid candidate"
                )
            if (
                self.candidate.price != self.source_bucket.price
                or self.candidate.available_quantity != self.source_bucket.liquidity
            ):
                raise OandaPricingProjectionError(
                    "OANDA pricing evidence candidate does not match its bucket"
                )

    @property
    def price(self) -> Decimal:
        """Expose the source price without duplicating the provider fact."""
        return self.source_bucket.price

    @property
    def available_quantity(self) -> Decimal:
        """Expose source liquidity using the provider-neutral candidate term."""
        return self.source_bucket.liquidity

    @property
    def is_candidate(self) -> bool:
        return self.candidate is not None


@dataclass(frozen=True, slots=True)
class OandaPracticeExecutablePricingProjection:
    """Required-side pricing facts and finite candidates for one direction."""

    observation: OandaPracticeEurUsdPricingObservation
    direction: Direction
    required_side: OandaPricingSide
    evidence: tuple[OandaPricingBucketEvidence, ...]
    candidates: tuple[OandaPracticeExecutablePriceCandidate, ...]

    def __post_init__(self) -> None:
        if type(self.observation) is not OandaPracticeEurUsdPricingObservation:
            raise OandaPricingProjectionError(
                "OANDA pricing projection has an invalid observation"
            )
        if type(self.direction) is not Direction:
            raise OandaPricingProjectionError(
                "OANDA pricing projection has an invalid direction"
            )
        expected_side: OandaPricingSide = (
            "asks" if self.direction is Direction.LONG else "bids"
        )
        if self.required_side != expected_side:
            raise OandaPricingProjectionError(
                "OANDA pricing projection has an invalid required side"
            )
        if type(self.evidence) is not tuple or any(
            type(item) is not OandaPricingBucketEvidence for item in self.evidence
        ):
            raise OandaPricingProjectionError(
                "OANDA pricing projection has invalid bucket evidence"
            )
        if type(self.candidates) is not tuple or any(
            type(item) is not OandaPracticeExecutablePriceCandidate
            for item in self.candidates
        ):
            raise OandaPricingProjectionError(
                "OANDA pricing projection has invalid candidates"
            )
        evidence_candidates = tuple(
            item.candidate for item in self.evidence if item.candidate is not None
        )
        if evidence_candidates != self.candidates:
            raise OandaPricingProjectionError(
                "OANDA pricing projection evidence does not match candidates"
            )

    @property
    def source_buckets(self) -> tuple[OandaPracticePriceBucket, ...]:
        """Return every required-side normalized source bucket."""
        return tuple(item.source_bucket for item in self.evidence)


def project_oanda_practice_executable_pricing(
    observation: OandaPracticeEurUsdPricingObservation,
    direction: Direction,
) -> OandaPracticeExecutablePricingProjection:
    """Project one normalized observation into finite required-side candidates.

    The source bucket collection is sorted only to make this projection
    independent of undocumented provider array ordering.  No bucket is
    aggregated and no final executable price is selected here.
    """
    if type(observation) is not OandaPracticeEurUsdPricingObservation:
        raise OandaPricingProjectionError(
            "OANDA pricing projection requires a normalized observation"
        )
    if type(direction) is not Direction:
        raise OandaPricingProjectionError(
            "OANDA pricing projection requires a Direction"
        )

    required_side: OandaPricingSide = "asks" if direction is Direction.LONG else "bids"
    source_buckets = tuple(
        sorted(
            getattr(observation, required_side),
            key=lambda bucket: (bucket.price, bucket.liquidity),
        )
    )
    evidence: list[OandaPricingBucketEvidence] = []
    candidates: list[OandaPracticeExecutablePriceCandidate] = []
    for source_bucket in source_buckets:
        candidate = (
            OandaPracticeExecutablePriceCandidate(
                price=source_bucket.price,
                available_quantity=source_bucket.liquidity,
            )
            if observation.tradeable and source_bucket.liquidity > 0
            else None
        )
        evidence.append(OandaPricingBucketEvidence(source_bucket, candidate))
        if candidate is not None:
            candidates.append(candidate)

    return OandaPracticeExecutablePricingProjection(
        observation=observation,
        direction=direction,
        required_side=required_side,
        evidence=tuple(evidence),
        candidates=tuple(candidates),
    )


__all__ = [
    "OandaPricingBucketEvidence",
    "OandaPricingProjectionError",
    "OandaPracticeExecutablePriceCandidate",
    "OandaPracticeExecutablePricingProjection",
    "project_oanda_practice_executable_pricing",
]
