from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from backend.domain.broker import (
    AccountIdentity,
    AccountSnapshot,
    ExecutableQuote,
    VenueInstrumentFacts,
)
from backend.domain.market_data import Instrument, Provider, VenueInstrument
from backend.domain.strategy import (
    Action,
    Direction,
    TargetMethodology,
    TargetProposal,
)
from backend.integrations.oanda.execution import OandaExecutionAdapter
from backend.risk import PaperRiskConfig, PaperRiskService, TradeIntent
from backend.runtime.coordinator import BrokerRead, RuntimeDeployment
from backend.runtime.production import PaperEntryAuthorizer, PendingPaperEntry

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def _instrument() -> VenueInstrumentFacts:
    return VenueInstrumentFacts(
        VenueInstrument(Instrument.EUR_USD, Provider.OANDA, "EUR_USD"),
        -4,
        5,
        0,
        Decimal("1"),
        Decimal("1000000"),
        Decimal("1000000"),
        Decimal("0.02"),
        frozenset({"LONG", "SHORT", "MARKET", "STOP_LOSS", "TAKE_PROFIT"}),
    )


def _read(account_id: str) -> BrokerRead:
    account = AccountSnapshot(
        AccountIdentity(account_id),
        Decimal("10000"),
        Decimal("10000"),
        Decimal("0"),
        Decimal("10000"),
        Decimal("9000"),
        Decimal("1000"),
        NOW,
        "recorded-oanda",
        orders_known=True,
        trades_known=True,
        positions_known=True,
    )
    quote = ExecutableQuote(
        Instrument.EUR_USD,
        Decimal("1.1000"),
        Decimal("1.1002"),
        NOW,
        "recorded-oanda",
        True,
    )
    return BrokerRead(account, _instrument(), quote)


class _Store:
    def __init__(self, pending: PendingPaperEntry) -> None:
        self.pending = pending
        self.persisted_phases: list[str] = []

    def pending_paper_entry(self, deployment_id):
        return self.pending

    def entry_order_resolution(self, deployment_id, intent_id):
        return None

    def paper_risk_config(self, deployment_id):
        return PaperRiskConfig(Decimal("0.01"))

    def reconciliation_facts(self, deployment_id):
        return {"position": {"state": "FLAT"}}

    def persist_risk_decision(self, intent_id, decision, evaluated_at):
        self.persisted_phases.append(decision.phase.value)
        return uuid4()

    def create_pending_order(self, *args, **kwargs):
        raise AssertionError("an invalid account read must not create an Order")

    def mark_entry_rejected(self, intent_id, reason):
        raise AssertionError(reason)


def _authorizer(reads: list[BrokerRead], store: _Store) -> PaperEntryAuthorizer:
    expected = AccountIdentity("selected-account")

    def reader(deployment, now):
        return reads.pop(0)

    return PaperEntryAuthorizer(
        store=cast(object, store),  # type: ignore[arg-type]
        broker_reader=reader,
        risk=PaperRiskService(),
        execution=OandaExecutionAdapter(),
        transport=cast(object, SimpleNamespace()),  # type: ignore[arg-type]
        capital_actions_enabled=True,
        clock=lambda: NOW,
        expected_account=expected,
    )


def _pending() -> PendingPaperEntry:
    return PendingPaperEntry(
        uuid4(),
        TradeIntent(
            Action.OPEN_LONG,
            Direction.LONG,
            Decimal("1.0950"),
            TargetProposal(TargetMethodology.R_MULTIPLE, Decimal("1.7")),
        ),
        uuid4(),
    )


def _deployment() -> RuntimeDeployment:
    return RuntimeDeployment(
        uuid4(),
        "selected-account",
        "RUNNING",
        "RUNNING",
        trading_account=AccountIdentity("selected-account"),
    )


def test_first_broker_read_for_wrong_account_blocks_before_risk() -> None:
    store = _Store(_pending())
    authorizer = _authorizer([_read("wrong-account")], store)

    with pytest.raises(ValueError, match="selected account"):
        authorizer(_deployment(), cast(object, SimpleNamespace()))  # type: ignore[arg-type]

    assert store.persisted_phases == []


def test_second_broker_read_is_revalidated_and_blocks_before_pre_submission() -> None:
    store = _Store(_pending())
    authorizer = _authorizer(
        [_read("selected-account"), _read("wrong-account")], store
    )

    with pytest.raises(ValueError, match="selected account"):
        authorizer(_deployment(), cast(object, SimpleNamespace()))  # type: ignore[arg-type]

    assert store.persisted_phases == ["PRE_FLIGHT"]


def test_broker_read_with_missing_account_identity_blocks() -> None:
    malformed = BrokerRead(
        cast(AccountSnapshot, SimpleNamespace(identity=None)),
        _instrument(),
        _read("selected-account").quote,
    )
    store = _Store(_pending())
    authorizer = _authorizer([malformed], store)

    with pytest.raises(ValueError, match="selected account"):
        authorizer(_deployment(), cast(object, SimpleNamespace()))  # type: ignore[arg-type]

    assert store.persisted_phases == []
