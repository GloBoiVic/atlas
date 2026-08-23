"""Focused persistence boundaries for canonical bars and dataset snapshots.

Repositories leave transaction ownership to their caller.  In particular, bar
application and snapshot creation are deliberately flush-only operations so a
caller can compose them in one PostgreSQL transaction.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.domain.market_data import (
    ALIGNMENT_CONVENTION,
    FINGERPRINT_SCHEMA,
    SESSION_POLICY,
    Bar,
    DatasetSnapshot,
    Instrument,
    PriceComponent,
    Provider,
    Timeframe,
    VenueInstrument,
)
from backend.market_data.fingerprint import dataset_fingerprint

from .models import (
    DatasetSnapshotBarModel,
    DatasetSnapshotModel,
    InstrumentModel,
    MarketBarModel,
    VenueInstrumentModel,
)

PERSISTED_M1_RESOLUTION = "M1"


def _encode_m1_resolution(timeframe: Timeframe) -> str:
    """Encode the domain timeframe into the task-5 database representation."""
    if timeframe is not Timeframe.M1:
        raise ValueError("only M1 bars may be persisted")
    return PERSISTED_M1_RESOLUTION


def _decode_resolution(value: str) -> Timeframe:
    """Decode the approved stored resolution without changing domain values."""
    if value != PERSISTED_M1_RESOLUTION:
        raise ValueError(f"unsupported persisted market-bar resolution: {value}")
    return Timeframe.M1


def _database_utc(value: datetime) -> datetime:
    """Normalize PostgreSQL timestamptz values before entering the domain."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class BarRange:
    start: datetime
    end: datetime
    components: tuple[PriceComponent, ...]


@dataclass(frozen=True, slots=True)
class BarBatchItem:
    bar: Bar
    retrieved_at: datetime
    source_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class BarBatchResult:
    inserted: int = 0
    reactivated: int = 0
    unchanged: int = 0


@dataclass(frozen=True, slots=True)
class SnapshotBarSourceIdentity:
    """Durable identity of the exact market-bar observation in a snapshot."""

    market_bar_id: UUID
    content_fingerprint: str
    source_request_id: str | None
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class SnapshotBar:
    """A snapshot member together with provenance needed by an Experiment."""

    bar: Bar
    source: SnapshotBarSourceIdentity


@dataclass(frozen=True, slots=True)
class SnapshotFrontier:
    """The two membership-bounded reads needed at one M1 frontier."""

    completed: tuple[SnapshotBar, ...]
    executable_opens: tuple[SnapshotBar, ...]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("repository timestamps must be UTC")
    return value


def _content_fingerprint(bar: Bar) -> str:
    payload = {
        "close": str(bar.close),
        "complete": True,
        "end_time": bar.end_time.isoformat(),
        "high": str(bar.high),
        "low": str(bar.low),
        "open": str(bar.open),
        "price_component": bar.price_component.value,
        "start_time": bar.start_time.isoformat(),
        "volume": None if bar.volume is None else str(bar.volume),
    }
    return sha256(
        (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()


def _venue(row: VenueInstrumentModel, instrument: InstrumentModel) -> VenueInstrument:
    return VenueInstrument(
        Instrument(instrument.code), Provider(row.provider), row.provider_symbol
    )


def _bar(row: MarketBarModel, venue: VenueInstrument) -> Bar:
    return Bar(
        instrument=venue.instrument,
        provider=venue.provider,
        timeframe=_decode_resolution(row.resolution),
        price_component=PriceComponent(row.price_component),
        start_time=_database_utc(row.start_time),
        end_time=_database_utc(row.end_time),
        open=row.open_price,
        high=row.high_price,
        low=row.low_price,
        close=row.close_price,
        volume=row.volume,
    )


class MarketDataRepository:
    """Append-only bar variants plus a serialized current projection."""

    def ensure_initial_venue_instrument(
        self, session: Session, venue: VenueInstrument
    ) -> VenueInstrumentModel:
        instrument = session.scalar(
            select(InstrumentModel).where(
                InstrumentModel.code == venue.instrument.value
            )
        )
        if instrument is None:
            session.execute(
                insert(InstrumentModel)
                .values(code="EUR/USD", base_currency="EUR", quote_currency="USD")
                .on_conflict_do_nothing(index_elements=[InstrumentModel.code])
            )
            instrument = session.scalar(
                select(InstrumentModel)
                .where(InstrumentModel.code == venue.instrument.value)
                .with_for_update()
            )
        else:
            session.refresh(instrument)
        if instrument is None:
            raise RuntimeError("instrument mapping could not be created")
        mapping = session.scalar(
            select(VenueInstrumentModel)
            .where(
                VenueInstrumentModel.instrument_id == instrument.id,
                VenueInstrumentModel.provider == venue.provider.value,
            )
            .with_for_update()
        )
        if mapping is None:
            session.execute(
                insert(VenueInstrumentModel)
                .values(
                    instrument_id=instrument.id,
                    provider=venue.provider.value,
                    provider_symbol=venue.provider_symbol,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        VenueInstrumentModel.instrument_id,
                        VenueInstrumentModel.provider,
                    ]
                )
            )
            mapping = session.scalar(
                select(VenueInstrumentModel)
                .where(
                    VenueInstrumentModel.instrument_id == instrument.id,
                    VenueInstrumentModel.provider == venue.provider.value,
                )
                .with_for_update()
            )
        if mapping is None:
            raise RuntimeError("venue instrument mapping could not be created")
        return mapping

    def current_bars(
        self,
        session: Session,
        venue_instrument_id: UUID,
        start: datetime,
        end: datetime,
        components: Sequence[PriceComponent],
    ) -> tuple[Bar, ...]:
        venue_row, instrument = self._venue_rows(session, venue_instrument_id)
        rows = session.scalars(
            select(MarketBarModel)
            .where(
                MarketBarModel.venue_instrument_id == venue_instrument_id,
                MarketBarModel.resolution == PERSISTED_M1_RESOLUTION,
                MarketBarModel.price_component.in_([c.value for c in components]),
                MarketBarModel.start_time >= start,
                MarketBarModel.start_time < end,
                MarketBarModel.is_current.is_(True),
            )
            .order_by(MarketBarModel.start_time, MarketBarModel.price_component)
        ).all()
        return tuple(_bar(row, _venue(venue_row, instrument)) for row in rows)

    def missing_ranges(
        self,
        session: Session,
        venue_instrument_id: UUID,
        start: datetime,
        end: datetime,
        components: Sequence[PriceComponent],
    ) -> tuple[BarRange, ...]:
        wanted = tuple(sorted(set(components), key=lambda c: c.value))
        existing = self.current_bars(session, venue_instrument_id, start, end, wanted)
        by_minute: dict[datetime, set[PriceComponent]] = {}
        for bar in existing:
            by_minute.setdefault(bar.start_time, set()).add(bar.price_component)
        ranges: list[BarRange] = []
        cursor = start
        while cursor < end:
            missing = tuple(c for c in wanted if c not in by_minute.get(cursor, set()))
            if missing:
                if (
                    ranges
                    and ranges[-1].end == cursor
                    and ranges[-1].components == missing
                ):
                    ranges[-1] = BarRange(
                        ranges[-1].start, cursor + timedelta(minutes=1), missing
                    )
                else:
                    ranges.append(
                        BarRange(cursor, cursor + timedelta(minutes=1), missing)
                    )
            cursor += timedelta(minutes=1)
        return tuple(ranges)

    def apply_bar_batch(
        self,
        session: Session,
        venue_instrument_id: UUID,
        items: Sequence[BarBatchItem],
    ) -> BarBatchResult:
        # This lock is the serialization point shared with snapshot creation.
        if (
            session.get(VenueInstrumentModel, venue_instrument_id, with_for_update=True)
            is None
        ):
            raise ValueError("venue instrument does not exist")
        inserted = reactivated = unchanged = 0
        session.flush()
        for item in items:
            bar = item.bar
            if bar.provider is not Provider.OANDA or bar.timeframe is not Timeframe.M1:
                raise ValueError("only OANDA M1 bars may be persisted")
            if (
                item.retrieved_at.tzinfo is None
                or item.retrieved_at.utcoffset() != timedelta(0)
            ):
                raise ValueError("retrieved_at must be UTC")
            fingerprint = _content_fingerprint(bar)
            logical = dict(
                venue_instrument_id=venue_instrument_id,
                resolution=_encode_m1_resolution(bar.timeframe),
                price_component=bar.price_component.value,
                start_time=bar.start_time,
            )
            variant = session.scalar(
                select(MarketBarModel).where(
                    *[
                        getattr(MarketBarModel, key) == value
                        for key, value in logical.items()
                    ],
                    MarketBarModel.content_fingerprint == fingerprint,
                )
            )
            current = session.scalar(
                select(MarketBarModel).where(
                    *[
                        getattr(MarketBarModel, key) == value
                        for key, value in logical.items()
                    ],
                    MarketBarModel.is_current.is_(True),
                )
            )
            if current is not None and current.content_fingerprint == fingerprint:
                unchanged += 1
                continue
            if current is not None:
                current.is_current = False
                # PostgreSQL's partial unique index requires the old
                # projection to be durable before another variant is made
                # current.  The surrounding transaction remains atomic.
                session.flush()
            if variant is None:
                session.add(
                    MarketBarModel(
                        **logical,
                        end_time=bar.end_time,
                        open_price=bar.open,
                        high_price=bar.high,
                        low_price=bar.low,
                        close_price=bar.close,
                        volume=bar.volume,
                        complete=True,
                        content_fingerprint=fingerprint,
                        source_request_id=item.source_request_id,
                        retrieved_at=item.retrieved_at,
                        is_current=True,
                    )
                )
                inserted += 1
            else:
                variant.is_current = True
                reactivated += 1
            session.flush()
        return BarBatchResult(inserted, reactivated, unchanged)

    def _venue_rows(
        self, session: Session, venue_id: UUID
    ) -> tuple[VenueInstrumentModel, InstrumentModel]:
        row = session.get(VenueInstrumentModel, venue_id)
        if row is None:
            raise ValueError("venue instrument does not exist")
        instrument = session.get(InstrumentModel, row.instrument_id)
        if instrument is None:  # pragma: no cover - protected by FK
            raise RuntimeError("venue instrument has no instrument")
        return row, instrument


class DatasetSnapshotRepository:
    """Atomic creation and immutable membership reads."""

    def by_fingerprint(self, session: Session, fingerprint: str) -> DatasetSnapshot:
        """Load a snapshot descriptor without consulting mutable bar heads."""
        row = session.scalar(
            select(DatasetSnapshotModel).where(
                DatasetSnapshotModel.fingerprint == fingerprint
            )
        )
        if row is None:
            raise ValueError("dataset snapshot does not exist")
        return self._to_domain(session, row)

    def list_options(self, session: Session) -> tuple[DatasetSnapshot, ...]:
        """Read immutable snapshot descriptors for configuration choices."""
        rows = session.scalars(
            select(DatasetSnapshotModel).order_by(
                DatasetSnapshotModel.created_at, DatasetSnapshotModel.id
            )
        ).all()
        return tuple(self._to_domain(session, row) for row in rows)

    def create_validated(
        self,
        session: Session,
        snapshot: DatasetSnapshot,
        bars: Sequence[MarketBarModel | UUID],
    ) -> DatasetSnapshot:
        mapping = session.scalar(
            select(VenueInstrumentModel)
            .join(InstrumentModel)
            .where(
                VenueInstrumentModel.provider
                == snapshot.venue_instrument.provider.value,
                VenueInstrumentModel.provider_symbol
                == snapshot.venue_instrument.provider_symbol,
                InstrumentModel.code == snapshot.venue_instrument.instrument.value,
            )
            .with_for_update()
        )
        if mapping is None:
            raise ValueError("snapshot venue instrument does not exist")
        ids = tuple(
            item.id if isinstance(item, MarketBarModel) else item for item in bars
        )
        rows = tuple(
            session.scalars(
                select(MarketBarModel).where(MarketBarModel.id.in_(ids))
            ).all()
        )
        if len(rows) != len(ids) or len(set(ids)) != len(ids):
            raise ValueError("snapshot membership contains missing or duplicate bars")
        if any(
            row.venue_instrument_id != mapping.id or not row.is_current for row in rows
        ):
            raise ValueError(
                "snapshot membership must contain current bars for one venue"
            )
        logical_members = {(row.start_time, row.price_component) for row in rows}
        if len(logical_members) != len(rows) or any(
            row.start_time < snapshot.coverage_start
            or row.start_time >= snapshot.coverage_end
            or row.end_time > snapshot.coverage_end
            for row in rows
        ):
            raise ValueError(
                "snapshot membership is outside its coverage or duplicated"
            )
        expected = snapshot.integrity_summary.get("bar_count")
        if expected != len(rows):
            raise ValueError("snapshot integrity bar_count does not match membership")
        instrument = session.get(InstrumentModel, mapping.instrument_id)
        if instrument is None:  # pragma: no cover - protected by FK
            raise RuntimeError("snapshot instrument does not exist")
        venue = _venue(mapping, instrument)
        actual_fingerprint = dataset_fingerprint(
            venue,
            snapshot.coverage_start,
            snapshot.coverage_end,
            snapshot.components,
            (_bar(row, venue) for row in rows),
            session_policy=snapshot.session_policy,
            alignment_convention=snapshot.alignment_convention,
        )
        if actual_fingerprint != snapshot.fingerprint:
            raise ValueError("snapshot fingerprint does not match membership")
        existing = session.scalar(
            select(DatasetSnapshotModel).where(
                DatasetSnapshotModel.fingerprint == snapshot.fingerprint
            )
        )
        if existing is not None:
            old_ids = set(
                session.scalars(
                    select(DatasetSnapshotBarModel.market_bar_id).where(
                        DatasetSnapshotBarModel.dataset_snapshot_id == existing.id
                    )
                ).all()
            )
            if old_ids != set(ids):
                raise ValueError(
                    "snapshot fingerprint already has different membership"
                )
            return self._to_domain(session, existing)
        row = DatasetSnapshotModel(
            id=snapshot.id,
            venue_instrument_id=mapping.id,
            base_resolution=_encode_m1_resolution(snapshot.base_resolution),
            components=[component.value for component in snapshot.components],
            coverage_start=snapshot.coverage_start,
            coverage_end=snapshot.coverage_end,
            alignment_convention=ALIGNMENT_CONVENTION,
            session_policy=SESSION_POLICY,
            fingerprint_schema=FINGERPRINT_SCHEMA,
            fingerprint=snapshot.fingerprint,
            integrity_summary=dict(snapshot.integrity_summary),
            created_at=snapshot.created_at,
        )
        session.add(row)
        session.flush()
        session.add_all(
            [
                DatasetSnapshotBarModel(
                    dataset_snapshot_id=row.id, market_bar_id=bar_id
                )
                for bar_id in ids
            ]
        )
        session.flush()
        return snapshot

    def members(self, session: Session, snapshot_id: UUID) -> tuple[Bar, ...]:
        return tuple(
            item.bar
            for item in self.ordered_members_with_sources(
                session, snapshot_id, None, None
            )
        )

    def ordered_members_with_sources(
        self,
        session: Session,
        snapshot_id: UUID,
        start: datetime | None,
        end: datetime | None,
        components: Sequence[PriceComponent] | None = None,
    ) -> tuple[SnapshotBar, ...]:
        """Read only immutable snapshot membership, ordered by minute/component.

        The join intentionally has no ``is_current`` predicate.  A later mutable
        correction may replace the current projection, but an Experiment must
        continue to read the exact MarketBar row captured by its snapshot.
        Ranges are half-open and must remain inside snapshot coverage.
        """
        snapshot = session.get(DatasetSnapshotModel, snapshot_id)
        if snapshot is None:
            raise ValueError("dataset snapshot does not exist")
        coverage_start = _database_utc(snapshot.coverage_start)
        coverage_end = _database_utc(snapshot.coverage_end)
        if start is None:
            start = coverage_start
        if end is None:
            end = coverage_end
        _utc(start)
        _utc(end)
        if start < coverage_start or end > coverage_end or end <= start:
            raise ValueError("snapshot read range is outside snapshot coverage")
        allowed = {PriceComponent(value) for value in snapshot.components}
        wanted = tuple(
            sorted(allowed, key=lambda component: component.value)
            if components is None
            else sorted(set(components), key=lambda component: component.value)
        )
        if not wanted or any(component not in allowed for component in wanted):
            raise ValueError("snapshot read requested unsupported price component")
        venue, instrument = self._snapshot_venue_rows(session, snapshot)
        rows = session.scalars(
            select(MarketBarModel)
            .join(
                DatasetSnapshotBarModel,
                DatasetSnapshotBarModel.market_bar_id == MarketBarModel.id,
            )
            .where(
                DatasetSnapshotBarModel.dataset_snapshot_id == snapshot_id,
                MarketBarModel.start_time >= start,
                MarketBarModel.start_time < end,
                MarketBarModel.price_component.in_([item.value for item in wanted]),
            )
            .order_by(MarketBarModel.start_time, MarketBarModel.price_component)
        ).all()
        return tuple(
            SnapshotBar(
                _bar(row, _venue(venue, instrument)),
                SnapshotBarSourceIdentity(
                    row.id,
                    row.content_fingerprint,
                    row.source_request_id,
                    _database_utc(row.retrieved_at),
                ),
            )
            for row in rows
        )

    def read_frontier(
        self, session: Session, snapshot_id: UUID, frontier: datetime
    ) -> SnapshotFrontier:
        """Read the completed M1 ending at T and executable opens starting at T."""
        _utc(frontier)
        completed = self.ordered_members_with_sources(
            session,
            snapshot_id,
            frontier - timedelta(minutes=1),
            frontier,
        )
        opens = self.ordered_members_with_sources(
            session,
            snapshot_id,
            frontier,
            frontier + timedelta(minutes=1),
            (PriceComponent.BID, PriceComponent.ASK),
        )
        return SnapshotFrontier(completed, opens)

    def _snapshot_venue_rows(
        self, session: Session, snapshot: DatasetSnapshotModel
    ) -> tuple[VenueInstrumentModel, InstrumentModel]:
        venue = session.get(VenueInstrumentModel, snapshot.venue_instrument_id)
        if venue is None:
            raise RuntimeError("snapshot venue instrument does not exist")
        instrument = session.get(InstrumentModel, venue.instrument_id)
        if instrument is None:
            raise RuntimeError("snapshot instrument does not exist")
        return venue, instrument

    def _to_domain(
        self, session: Session, row: DatasetSnapshotModel
    ) -> DatasetSnapshot:
        venue_row = session.get(VenueInstrumentModel, row.venue_instrument_id)
        if venue_row is None:
            raise RuntimeError("snapshot venue instrument does not exist")
        instrument = session.get(InstrumentModel, venue_row.instrument_id)
        if instrument is None:
            raise RuntimeError("snapshot instrument does not exist")
        return DatasetSnapshot(
            id=row.id,
            venue_instrument=_venue(venue_row, instrument),
            base_resolution=_decode_resolution(row.base_resolution),
            components=tuple(PriceComponent(value) for value in row.components),
            coverage_start=_database_utc(row.coverage_start),
            coverage_end=_database_utc(row.coverage_end),
            alignment_convention=row.alignment_convention,
            session_policy=row.session_policy,
            fingerprint_schema=row.fingerprint_schema,
            fingerprint=row.fingerprint,
            integrity_summary=dict(row.integrity_summary),
            created_at=_database_utc(row.created_at),
        )


__all__ = [
    "BarBatchItem",
    "BarBatchResult",
    "BarRange",
    "DatasetSnapshotRepository",
    "MarketDataRepository",
    "PERSISTED_M1_RESOLUTION",
    "SnapshotBar",
    "SnapshotBarSourceIdentity",
    "SnapshotFrontier",
]
