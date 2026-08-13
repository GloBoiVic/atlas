# Execution

## Purpose

Convert approved TradeIntent into canonical Orders, submit through broker/simulator adapter, process broker truth, update state from actual Fills. Initial: OANDA Practice, EUR/USD, PAPER. Must remain safe under retries, timeouts, reconnects, partial fills.

## Core Flow

TradeIntent → PRE_FLIGHT RiskDecision → executable context → PRE_SUBMISSION RiskDecision → Order → Execution Adapter → broker/simulator → OrderEvent → Fill → Position/Trade update. Strategies never submit Orders directly.

## Canonical Boundary / Order

Core depends on narrow execution interface. Initial: SimulatedExecutionAdapter, OandaExecutionAdapter. Provider-specific models inside adapter. No environment-specific Order models. Canonical Order: Atlas ID, TradeIntent, context, Instrument, side, type, quantity, purpose, protection, status, stable client correlation ID, external broker ID, timestamps. [Domain Model](../architecture/domain-model.md).

## Order Types / Purpose / Stable Identity

Initial types: MARKET, STOP, LIMIT (for entries, stop-loss, take-profit). Purposes: ENTRY, EXIT, STOP_LOSS, TAKE_PROFIT, PROTECTION_UPDATE. Atlas Order identity independent of OANDA IDs. Use: Atlas ID + stable client correlation ID + external broker ID when known. Supports retries and reconciliation.

## Submission State / Idempotency

Persist PENDING_SUBMISSION before external request. Commit → submit externally. No DB transaction open during network call. **Order submission must be retry-safe.** Never: timeout → submit again immediately. Instead: submit → timeout/uncertain → mark UNKNOWN → reconcile → determine Order existence → retry only if absence established and safe. Duplicate exposure is critical defect.

## Client Correlation / External IDs

Stable identifier tied to canonical Order, same across retry/reconciliation. Persist broker IDs (external Order ID, transaction ID, Fill/execution ID) for reconciliation, deduplication, diagnostics, auditability. Not exposed as normal product identity.

## Fill-Driven State

**Fill received → update Order → Position → Trade → accounting.** Not: Order submitted → assume Position exists. Requested quantity ≠ executed quantity.

## Partial Fills

Core must tolerate: Order qty 100,000, Fill 40,000 → Order PARTIALLY_FILLED, Position 40,000. No fabricating full Position from requested amount. v1 doesn't support Strategy-level partial exits; broker partial Fills are still real. SimulatedExecutionAdapter may assume full fills in initial simulator — does not change canonical domain's multiple-Fill support.

## Entry Execution / Forex Side

EMA Sweep Engulfing: completed 15m confirmation → OPEN_LONG/SHORT → Risk → MARKET entry Order. Entry only on first eligible post-decision observation. No retrospective fill at signal close. Long entry BUY→ASK, exit SELL→BID. Short entry SELL→BID, exit BUY→ASK. Canonical pricing: [Market Data Model](../architecture/market-data-model.md).

## Stop / Target Reference

Long stop: confirmation low - 0.5 ATR. Short stop: confirmation high + 0.5 ATR. Risk validates geometry. Execution translates approved protection into broker-native instructions. Target: 1.7R based on actual entry and approved stop. Execution does not recalculate Strategy methodology.

## Broker-Hosted Protection

For PAPER/LIVE: use broker-hosted protection where OANDA supports it. Safety must not depend solely on Atlas uptime. Required: Stop Loss + Take Profit. Establish as close to entry as broker semantics permit. Prefer atomic/attached mechanisms. If protection requires follow-up → explicitly handle interval between entry and confirmed protection.

## Protection Failure / Confirmation / Cancellation

Entry exists but protection unconfirmed → **critical condition**: block new exposure, Deployment FAILED or RECONCILIATION_REQUIRED, persist safety event, attempt only defined risk-reducing recovery. No silent unprotected Position. Do not treat locally persisted stop/target as proof of broker protection — confirm authoritative state. When protective exit closes Position: ensure remaining conflicting protection can't create unintended exposure. No orphan target/stop capable of reversing.

## Closing Fills / Position State / Trade / Atomicity

Closing Fill(s) → zero exposure → Position FLAT → Trade CLOSED. Persist canonical exit reason (STOP_LOSS, TAKE_PROFIT). Position derives from Fills per Domain Model. Trade opens/closes with Fills. Process confirmed Fill: atomically persist Fill + Order state + Position + Trade + simulated/local accounting. Not held open during new external requests.

## Cancellation / Rejection / Unknown

Request cancel → broker confirms → CANCELED. Uncertain broker state → UNKNOWN → reconcile. No assume success after timeout. OANDA rejection → Order REJECTED. Preserve canonical reason + broker diagnostic + timestamp. No Position without Fill.

## Broker Error Mapping / Unknown State / OANDA Practice

Map: AUTHENTICATION_ERROR, INVALID_ORDER, INSUFFICIENT_MARGIN, MARKET_UNAVAILABLE, RATE_LIMITED, NETWORK_ERROR, BROKER_REJECTED. No enormous taxonomy. UNKNOWN → reconcile per Safety Model. PAPER uses actual OANDA Practice API — not fake engine. Historical → SimulatedExecutionAdapter. Live → same OANDA path; environment config determines destination.

## Manual Close / Execution & Risk / Adapters

Manual close (future): uses canonical execution, explicitly risk-reducing, preserves provenance, no browser-to-broker shortcuts. Only successful PRE_SUBMISSION authorizes new entry. No independent quantity/Rule invention by execution. SimulatedExecutionAdapter follows canonical Order/Fill semantics with Experiment assumptions. OandaExecutionAdapter: request translation, provider-native models, IDs, API calls, response normalization, error translation — returns canonical facts.

## Adapter Scope / Runtime / Persistence / Audit

Narrow explicit boundary; one OANDA implementation. No ExecutionAdapterFactoryRegistry/UniversalBrokerOrderDSL/BrokerPluginManager for one broker. Only atlas-runtime submits automated Orders. Explicit stages: persist PENDING_SUBMISSION → external → normalize → persist result. Uncertainty → reconciliation repairs. Execution traceable through canonical identifiers (Deployment, TradeIntent, RiskDecision, Order, external ID, Fill, Trade). Not dependent only on logs.

## UI / Safety UX

Execution detail progressively disclosed in Trade Detail. Raw OANDA payloads in technical diagnostics, not primary UI. Material problems remain visible (Order state unknown, protection missing, rejected, reconciliation required). Not Sonner-only.

## Non-Goals

No smart-order routing, multiple brokers, limit-entry Strategies, trailing stops, partial exits, pyramiding, execution algorithms, order slicing, market making, HFT infrastructure, distributed execution, generic plugin framework.

## Required Tests

Canonical Order creation, stable correlation ID, PENDING_SUBMISSION persistence, successful OANDA Practice entry normalization, BUY/SELL behavior, rejected Order, cancellation confirmation + timeout→UNKNOWN, submission timeout with Order found/absent, no blind duplicate retry, full/partial Fill, Position from executed quantity, Trade opens/closes from Fill, broker-hosted stop/target request, protection confirmation + failure after entry, orphan prevention, Fill transactionality, both adapters use canonical Order/Fill model. Live credential tests separate.

## Acceptance Flow

Completed live 15m bar → TradeIntent → PRE_FLIGHT → executable context → PRE_SUBMISSION → canonical ENTRY Order persisted → OANDA submission → normalized response → Fill → Position → broker-hosted stop+target confirmed → protective exit Fill → Position FLAT → Trade closed.

## Success Criteria

For first PAPER milestone: safely convert approved TradeIntent into real OANDA Practice Trade, derive exposure only from broker-confirmed Fills, maintain broker-hosted protection, survive submission uncertainty without creating duplicate exposure.
