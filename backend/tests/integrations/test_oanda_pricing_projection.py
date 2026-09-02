from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.domain.market_data import Provider
from backend.domain.strategy import Direction
from backend.integrations.oanda import (
    OandaPracticeAccountIdentity,
    OandaPracticeEurUsdPricingObservation,
    OandaPracticeExecutablePriceCandidate,
    OandaPracticePriceBucket,
    OandaPricingProjectionError,
    project_oanda_practice_executable_pricing,
)

ACCOUNT_ID = "001-011-5838423-001"


def identity() -> OandaPracticeAccountIdentity:
    return OandaPracticeAccountIdentity(
        provider=Provider.OANDA,
        environment="PRACTICE",
        provider_account_id=ACCOUNT_ID,
        alias="Research Practice",
        base_currency="USD",
    )


def observation(
    *,
    tradeable: bool = True,
    bids: tuple[OandaPracticePriceBucket, ...] = (),
    asks: tuple[OandaPracticePriceBucket, ...] = (),
) -> OandaPracticeEurUsdPricingObservation:
    return OandaPracticeEurUsdPricingObservation(
        identity=identity(),
        provider_instrument="EUR_USD",
        price_time=datetime(2026, 8, 31, 12, 34, tzinfo=UTC),
        tradeable=tradeable,
        bids=bids,
        asks=asks,
    )


def bucket(price: str, liquidity: str) -> OandaPracticePriceBucket:
    return OandaPracticePriceBucket(Decimal(price), Decimal(liquidity))


def test_long_projects_asks_only_and_retains_zero_liquidity_evidence() -> None:
    result = project_oanda_practice_executable_pricing(
        observation(
            bids=(bucket("1.0999", "900"),),
            asks=(bucket("1.1002", "0"), bucket("1.1003", "2000")),
        ),
        Direction.LONG,
    )

    assert result.required_side == "asks"
    assert result.source_buckets == (
        bucket("1.1002", "0"),
        bucket("1.1003", "2000"),
    )
    assert result.candidates == (
        OandaPracticeExecutablePriceCandidate(Decimal("1.1003"), Decimal("2000")),
    )
    assert [item.is_candidate for item in result.evidence] == [False, True]
    assert result.evidence[0].available_quantity == Decimal("0")


def test_short_projects_bids_only_when_opposite_asks_are_empty() -> None:
    result = project_oanda_practice_executable_pricing(
        observation(
            bids=(bucket("1.1000", "1000"), bucket("1.0998", "500")),
            asks=(),
        ),
        Direction.SHORT,
    )

    assert result.required_side == "bids"
    assert result.candidates == (
        OandaPracticeExecutablePriceCandidate(Decimal("1.0998"), Decimal("500")),
        OandaPracticeExecutablePriceCandidate(Decimal("1.1000"), Decimal("1000")),
    )


@pytest.mark.parametrize(
    ("direction", "bids", "asks"),
    [
        (Direction.LONG, (), ()),
        (Direction.SHORT, (), ()),
        (
            Direction.LONG,
            (bucket("1.1000", "100"),),
            (bucket("1.1002", "0"),),
        ),
        (
            Direction.SHORT,
            (bucket("1.1000", "0"),),
            (bucket("1.1002", "100"),),
        ),
    ],
)
def test_empty_or_nonpositive_required_side_has_no_candidates(
    direction: Direction,
    bids: tuple[OandaPracticePriceBucket, ...],
    asks: tuple[OandaPracticePriceBucket, ...],
) -> None:
    result = project_oanda_practice_executable_pricing(
        observation(bids=bids, asks=asks), direction
    )

    assert result.candidates == ()
    assert all(not item.is_candidate for item in result.evidence)


def test_nontradeable_price_retains_required_side_but_has_no_candidates() -> None:
    result = project_oanda_practice_executable_pricing(
        observation(
            tradeable=False,
            bids=(bucket("1.1000", "1000"),),
            asks=(bucket("1.1002", "2000"),),
        ),
        Direction.LONG,
    )

    assert result.candidates == ()
    assert result.source_buckets == (bucket("1.1002", "2000"),)
    assert result.evidence[0].candidate is None


def test_projection_is_source_order_invariant_and_does_not_aggregate() -> None:
    first = project_oanda_practice_executable_pricing(
        observation(
            asks=(
                bucket("1.1003", "10"),
                bucket("1.1001", "20"),
                bucket("1.1003", "5"),
            )
        ),
        Direction.LONG,
    )
    reversed_source = project_oanda_practice_executable_pricing(
        observation(
            asks=(
                bucket("1.1003", "5"),
                bucket("1.1001", "20"),
                bucket("1.1003", "10"),
            )
        ),
        Direction.LONG,
    )

    assert first.direction == reversed_source.direction
    assert first.required_side == reversed_source.required_side
    assert first.evidence == reversed_source.evidence
    assert first.candidates == reversed_source.candidates
    assert len(first.candidates) == 3
    assert first.candidates[0].available_quantity == Decimal("20")
    assert first.candidates[1].available_quantity == Decimal("5")
    assert first.candidates[2].available_quantity == Decimal("10")


def test_projection_and_candidates_are_immutable() -> None:
    result = project_oanda_practice_executable_pricing(
        observation(asks=(bucket("1.1002", "2000"),)), Direction.LONG
    )

    with pytest.raises(FrozenInstanceError):
        result.candidates[0].__setattr__("price", Decimal("1.2"))
    with pytest.raises(FrozenInstanceError):
        result.__setattr__("candidates", ())


@pytest.mark.parametrize("value", [object(), None])
def test_projection_rejects_non_normalized_inputs(value: object) -> None:
    with pytest.raises(OandaPricingProjectionError):
        project_oanda_practice_executable_pricing(value, Direction.LONG)  # type: ignore[arg-type]


def test_candidate_rejects_nonpositive_or_nonfinite_values() -> None:
    with pytest.raises(OandaPricingProjectionError):
        OandaPracticeExecutablePriceCandidate(Decimal("0"), Decimal("1"))
    with pytest.raises(OandaPricingProjectionError):
        OandaPracticeExecutablePriceCandidate(Decimal("1"), Decimal("0"))
    with pytest.raises(OandaPricingProjectionError):
        OandaPracticeExecutablePriceCandidate(Decimal("NaN"), Decimal("1"))
