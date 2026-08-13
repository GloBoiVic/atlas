# Trading Accounts

## Purpose

Connect Atlas to external broker accounts for PAPER or LIVE trading. Initial: OANDA, Practice/PAPER, USD, EUR/USD. Establishes account identity, connection, capabilities, normalized state. Does not submit Strategy Orders.

## Core Model

TradingAccount for external broker accounts. Canonical: [Domain Model](../architecture/domain-model.md). Historical Experiments do not create TradingAccounts.

## Initial Account / Modes

One OANDA Practice account initially. Maps to PAPER. No multi-account complexity. Modes: PAPER and LIVE. OANDA Practice → PAPER. OANDA Live → LIVE.

## OANDA Boundary

OANDA-specific behavior (account identifiers, API URLs, auth, Instrument names, response schemas, capabilities, Order/Position representations) inside OANDA integration layer. No OANDA DTOs throughout domain.

## Configuration / Connection Validation

Requires only what's necessary: API token, account identifier, environment. Secrets from secure config — no plaintext tokens in DB, logs, or API responses. Validation: credentials valid, account reachable, mode known, base currency known, EUR/USD available, required capabilities available. No Order submitted during validation.

## Normalized State / Broker Authority

Normalize broker state for Risk and monitoring: balance, NAV/equity, unrealized P&L, margin used/available, open Positions, pending Orders. Canonical Atlas representations. Preserve provider values only for provenance/reconciliation. Broker authority: [Safety Model](../architecture/safety-model.md). OANDA authoritative for actual state; uncertainty blocks new exposure.

## Base Currency / Instrument / Capabilities

Initial: USD. Not hardcoded in generic domain logic. Confirm TradingAccount can trade EUR/USD via VenueInstrument. Normalize Instrument constraints (precision, min size, price precision, tradeability, margin info). Capabilities: MARKET_ORDER, STOP_LOSS, TAKE_PROFIT, LONG, SHORT — explicit and small.

## Account State Refresh / Persistence

REST initially; no streaming until required. Persist: broker, external ID, canonical mode, base currency, display name, non-secret config, capability metadata. Cached balance/equity not immutable facts.

## Display Name / UI / Connection Status

Normal UI: meaningful label ("OANDA Practice"). Not raw external IDs. Settings/account presentation small: mode, base currency, Instrument, status, actions (Test Connection, Refresh). Not institutional management dashboard. Healthy connection compact. Status prominent when degraded.

## Disconnection / Snapshot / Positions / Orders

If OANDA unreachable: state uncertain. Don't assume cached authoritative. Normalized current account snapshot for Runtime/Risk (balance, equity, margin, Positions, timestamp) — not competing TradingAccount identity. OANDA Position data normalized for account inspection/Risk/validation. Do not create/mutate Atlas Position via this feature — belongs to Execution/Deployment. OANDA pending Orders read-only as authoritative state; no submit/cancel/modify here.

## Environment Safety / Provider Errors / Timeouts

UI clearly identifies PAPER for Practice; LIVE support must not share PAPER presentation. Translate provider failures to useful errors: "Cannot connect — authentication rejected. Check token." No raw provider payloads to users. Distinguish auth failure, unavailable service, timeout, malformed response, unsupported capability where meaningful.

## Rate Limits / API Contract / Future Brokers / LIVE / Crypto

Adapter respects provider rate limits; no generalized rate-limit platform. Frontend/API use canonical TradingAccount info — no credentials, raw DTOs, unnecessary external IDs. Architecture permits another broker later; no BrokerPluginManager, DynamicBrokerRegistry, UniversalBrokerFramework before second broker. LIVE deferred until PAPER proven; reuse same TradingAccount model with mode=LIVE. Crypto outside initial scope.

## Non-Goals

No OANDA Live, multiple brokers/accounts, account switching, broker account creation, deposits/withdrawals, portfolio management, automated Orders, reconciliation engine, streaming events, crypto, broker plugin framework.

## Required Tests

Valid OANDA Practice connection, invalid credentials, timeout/unavailable, Practice→PAPER normalization, USD base currency, EUR/USD availability, VenueInstrument mapping, account-state normalization, Instrument metadata, capability validation, secret exclusion, provider error translation, broker authority, unavailable state blocks new exposure eligibility. Credential-dependent tests separate from deterministic suite.

## Acceptance Flow

Configure OANDA Practice → Atlas validates → identity retrieved → Practice normalized to PAPER → USD confirmed → EUR/USD confirmed → capabilities confirmed → state normalized → Connected displayed. No Strategy Order submitted.

## Success Criteria

Reliably answer: Which account connected? PAPER or LIVE? Reachable? Authoritative current state? Can trade EUR/USD? Supports Strategy requirements? — without coupling rest of Atlas directly to OANDA.
