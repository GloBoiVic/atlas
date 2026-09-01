"""Read-only OANDA composition for PAPER reconciliation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import cast

from backend.domain.broker import AccountSnapshot, BrokerProtectionFact
from backend.integrations.oanda.normalization import (
    normalize_account_changes,
    normalize_account_selection,
    normalize_account_snapshot,
    normalize_executable_quote,
    normalize_instrument_facts,
    normalize_trade_protection,
)
from backend.integrations.oanda.readonly import OandaReadOnlyTransport
from backend.runtime.coordinator import BrokerRead, RuntimeDeployment


def _identity_set(payload: Mapping[str, object], key: str) -> set[str]:
    values = cast(object, payload.get(key))
    if not isinstance(values, list):
        raise ValueError(f"broker {key} collection is unavailable")
    result: set[str] = set()
    for raw_value in cast(list[object], values):
        if not isinstance(raw_value, Mapping):
            raise ValueError(f"broker {key} identity is invalid")
        value = cast(Mapping[str, object], raw_value)
        if not isinstance(value.get("id"), str):
            raise ValueError(f"broker {key} identity is invalid")
        result.add(cast(str, value["id"]))
    return result


class OandaReadOnlyBrokerReader:
    """Compose normalized account/instrument/quote facts using GET only."""

    def __init__(
        self,
        transport: OandaReadOnlyTransport,
        *,
        protection_checker: Callable[[RuntimeDeployment, AccountSnapshot], bool]
        | None = None,
        transaction_cursor: Callable[[RuntimeDeployment], str | None] | None = None,
    ) -> None:
        self.transport = transport
        self.protection_checker = protection_checker
        self.transaction_cursor = transaction_cursor

    def read(self, deployment: RuntimeDeployment, now: datetime) -> BrokerRead:
        account_id = deployment.account_id
        selection = normalize_account_selection(
            self.transport.list_accounts(), account_id
        )
        account_payload = self.transport.account_summary(account_id)
        account = normalize_account_snapshot(
            account_payload, selection, observed_at=now
        )
        orders_reader = getattr(self.transport, "orders", None)
        if callable(orders_reader):
            order_ids = _identity_set(
                cast(Mapping[str, object], orders_reader(account_id)), "orders"
            )
            summary_order_ids = {item.external_id for item in account.pending_orders}
            if order_ids != summary_order_ids:
                raise ValueError("broker pending Order facts disagree")
        trades_reader = getattr(self.transport, "open_trades", None)
        if callable(trades_reader):
            trade_ids = _identity_set(
                cast(Mapping[str, object], trades_reader(account_id)), "trades"
            )
            summary_trade_ids = {item.external_id for item in account.open_trades}
            if trade_ids != summary_trade_ids:
                raise ValueError("broker open Trade facts disagree")
        instrument = normalize_instrument_facts(
            self.transport.instrument(account_id, "EUR_USD")
        )
        quote = normalize_executable_quote(
            self.transport.pricing(account_id, "EUR_USD")
        )
        protection_facts = ()
        if self.protection_checker is not None:
            protection_verified = self.protection_checker(deployment, account)
        else:
            protection_verified = not account.has_open_position
            trade_reader = getattr(self.transport, "trade", None)
            if callable(trade_reader) and account.open_trades:
                facts: list[BrokerProtectionFact] = []
                try:
                    for trade in account.open_trades:
                        facts.append(
                            normalize_trade_protection(
                                cast(
                                    Mapping[str, object],
                                    trade_reader(account_id, trade.external_id),
                                ),
                                observed_at=account.observed_at,
                            )
                        )
                except Exception:
                    protection_verified = False
                else:
                    protection_facts = tuple(facts)
                    protection_verified = len(facts) == len(account.open_trades)

        # The account Details/Summary response is the authoritative current
        # snapshot used to establish a cursorless flat baseline.  It is not an
        # Account Changes response, so it must never be represented as known
        # transaction history or cause a synthetic ``since`` request.
        transactions = ()
        transactions_known = False
        transaction_reader = getattr(self.transport, "account_changes", None)
        transaction_fence = account.last_transaction_id
        since_id = (
            self.transaction_cursor(deployment)
            if self.transaction_cursor is not None
            else None
        )
        if since_id is not None and (
            type(since_id) is not str or not since_id.isdecimal()
        ):
            raise ValueError("durable Account Changes cursor is invalid")
        # A brand-new flat Deployment establishes its bounded cursor baseline
        # from the current account reconciliation; it must not import history.
        if callable(transaction_reader) and since_id is not None:
            changes = normalize_account_changes(
                cast(
                    Mapping[str, object],
                    transaction_reader(account_id, since_id),
                ),
                expected_account_id=deployment.account_id,
            )
            if changes.account_id != deployment.account_id:
                raise ValueError("Account Changes account binding disagrees")
            transactions = changes.transactions
            transaction_fence = changes.last_transaction_id
            transactions_known = True
        return BrokerRead(
            account=account,
            instrument=instrument,
            quote=quote,
            protection_verified=protection_verified,
            protection_facts=protection_facts,
            transactions=transactions,
            transactions_known=transactions_known,
            transaction_fence=transaction_fence,
        )


__all__ = ["OandaReadOnlyBrokerReader"]
