# Feature: 09 — Binance Testnet Trading

## Description

Execute trades through broker adapters after the Binance Spot paper-trading slice is stable. The first implementation targets Binance Spot testnet only; production trading and Oanda are deferred.

## Dependencies

- 07 — Execution Layer
- 08 — Live Data Streaming

## Deliverables

- [ ] Binance Spot testnet broker adapter: Place orders via ccxt
- [ ] Broker authentication: Read credentials from server environment secrets
- [ ] Testnet order execution: Submit, fill, cancel, and reconcile orders
- [ ] Position tracking: Sync net positions with the broker before resuming bots
- [ ] Explicit mode boundary: paper and testnet use separate account/configuration records

## Technical Details

Oanda execution is deferred until the Binance Spot testnet workflow is stable. Its adapter contract will be specified when scheduled.

### Binance Broker Adapter

```python
class BinanceBroker(Broker):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.exchange = ccxt.async_support.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "options": {"defaultType": "spot"},
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)

    async def submit_order(self, order: Order) -> OrderResult:
        symbol = self._to_binance_symbol(order.instrument)
        side = "buy" if order.side == SignalDirection.BUY else "sell"
        try:
            result = await self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=self._format_quantity(order.quantity),
            )
            return OrderResult(success=True, order_id=result["id"])
        except Exception as e:
            return OrderResult(success=False, error=str(e))
```

### Configuration

```yaml
broker:
  name: "binance"
  mode: "testnet"  # or "paper"

  binance:
    api_key: "${BINANCE_API_KEY}"
    api_secret: "${BINANCE_API_SECRET}"

  oanda:
    api_key: "${OANDA_API_KEY}"
    account_id: "${OANDA_ACCOUNT_ID}"
```

## Acceptance Criteria

- [ ] Binance Spot testnet orders can be submitted, filled, cancelled, and reconciled
- [ ] Positions are tracked correctly as one net position per account and instrument
- [ ] Broker authentication uses server environment secrets and never reaches the browser
- [ ] Testnet mode cannot accidentally use production endpoints or credentials
- [ ] Unknown order responses trigger reconciliation before retry
- [ ] Paper and testnet accounts cannot share orders or positions

## Done when

All acceptance criteria are met.
