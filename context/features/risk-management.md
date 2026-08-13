# Risk Management

## Purpose

Risk Management decides whether Atlas may take a trade and how much exposure is allowed. Strategy defines trade structure; Risk controls capital. Initial implementation intentionally small, expanding only when roadmap requires.

## Core Rule

Strategy: direction, stop, target, entry rationale. Risk: trade eligibility, account safety, risk amount, submit quantity. A Strategy must never size itself from account equity.

## Same Risk Logic Everywhere

Same canonical Risk across Experiment, PAPER, LIVE. Account-state source changes; methodology does not. [Domain Model](../architecture/domain-model.md).

## Risk Inputs / RiskProfile

Risk receives explicit inputs: TradeIntent, account/equity state, Position/exposure, Risk configuration, executable context, Instrument constraints, Deployment/Experiment eligibility. No hidden DB/broker queries deep inside calculations. RiskProfile: reusable policy (risk_per_trade, max_open_positions, daily_loss_limit, max_drawdown). Not all fields implemented in first slice. Experiments and Deployments preserve immutable Risk snapshots.

## Initial Risk Scope

First Trade: risk_per_trade, valid stop geometry, no existing Position, valid quantity. Enough to prove centralized Risk. Do not delay first Experiment for every future control.

## Risk Per Trade / Position Sizing

current equity × risk_per_trade = risk budget. Strategy does not receive this value. risk budget ÷ loss per unit at stop = raw quantity. Apply Instrument precision, min/max, venue rules, margin constraints. Conservative rounding — never increase intended Risk beyond budget. Deterministic and tested.

## Forex Risk

May require entry/stop prices, units, quote/base currency, account conversion. Initial EUR/USD + USD simpler. Not hardcoded into generic Risk.

## Stop Geometry / Target

Long: stop < entry. Short: stop > entry. Invalid → REJECTED. Risk does not choose reference Strategy's target (1.7R for EMA Sweep Engulfing) — may validate internal validity.

## Two-Stage Risk

**PRE_FLIGHT** (after TradeIntent): is trade eligible in principle? Checks: Deployment/Experiment allows entry, no existing Position, account state available, Risk config valid, stop structure valid, account limits not breached. Does not finalize quantity if price unknown.
**PRE_SUBMISSION** (immediately before Order): still safe at actual executable market? Uses current price, equity, Position, Instrument rules, approved stop, Risk limits. Final authority before new exposure.

## Market Movement

TradeIntent may pass PRE_FLIGHT and fail PRE_SUBMISSION (market moved, stop geometry invalid). No submission based on stale Risk calculations.

## RiskDecision / Rejection Reasons

Persist RiskDecision: phase, TradeIntent, outcome, Risk config, risk budget/quantity where approved, rejection reason, timestamp. Outcomes: APPROVED, REJECTED. Canonical reasons: POSITION_ALREADY_OPEN, INVALID_STOP, INVALID_QUANTITY, ACCOUNT_STATE_UNKNOWN, DEPLOYMENT_NOT_RUNNING, RISK_LIMIT_REACHED, INSUFFICIENT_MARGIN. UI may translate.

## Existing Position / Quantity Validation

No pyramiding. Position exists → OPEN_LONG/OPEN_SHORT → REJECTED. Final quantity complies with Instrument/venue constraints (min size, precision, increment, max). Broker adapter provides constraints. Risk owns final quantity.

## Margin / Account State / Position State

For PAPER/LIVE: normalized broker margin constraints. Cannot establish → REJECTED. No guessing. Account state: [Accounting Model](../architecture/accounting-model.md). Risk must not depend directly on OANDA. Unknown account/position state → REJECTED per [Safety Model](../architecture/safety-model.md).

## Max Open Positions / Daily Loss / Max Drawdown

Future RiskProfile may limit account-wide Positions. Initially naturally constrained by Deployment ownership. Daily-loss blocking is later hardening; policy must explicitly define day boundary, timezone, realized vs total loss, reset. Max drawdown also later; threshold breached → block new exposure (no automatic liquidation unless separate policy).

## Risk-Reducing Actions / PAUSED/FAILED / Experiment

Risk blocks must not trap existing exposure. Safety follow: [Safety Model](../architecture/safety-model.md). For Deployment PAUSED/FAILED/RECONCILIATION_REQUIRED: new entry blocked; risk-reducing actions may remain. Experiments: persist rejected TradeIntents/RiskDecisions for analysis. Distinguish "no intent produced" from "intent rejected by Risk." Rejected intent ≠ Trade.

## PAPER/LIVE / Strategy Independence / Instrument Economics

Same Risk rules for PAPER and LIVE. PAPER must not bypass account-state, stop, sizing, or safety checks — it's the proving environment. Strategy never receives risk_per_trade, balance, equity, margin, drawdown state. Centralize pip-value and currency-conversion calculations — not scattered across Strategy/UI/adapter/Risk.

## Currency Conversion / Risk UI / Visibility

Account base currency differs from Instrument P&L currency → deterministic conversion. Initial EUR/USD+USD simpler; preserve boundary without building all paths. Risk config simple: expose only implemented controls. Where useful: Risk Per Trade, Risk Budget, Quantity for Trade/decision inspection. Not overwhelming primary views.

## Rejection UX / Auditability

Explain why: "Trade rejected — stop above long entry price at current executable price." Trader traces: TradeIntent → PRE_FLIGHT → PRE_SUBMISSION → Order without raw logs.

## Non-Goals

No portfolio VaR, correlation risk, sector exposure, multi-account allocation, dynamic Kelly, volatility targeting, trailing account risk, automatic deleveraging, institutional margin, Risk optimization, Strategy-specific sizing.

## Required Tests

Valid long/short sizing, risk-per-trade budget, deterministic quantity, conservative rounding, invalid long/short stop, existing Position rejection, account state unknown rejection, invalid quantity rejection, PRE_FLIGHT/PRE_SUBMISSION approval, PRE_SUBMISSION rejection after market movement, same core logic in Experiment and PAPER.

## Acceptance Flow

TradeIntent → PRE_FLIGHT APPROVED → post-decision executable price → PRE_SUBMISSION → calculate risk budget + valid quantity → APPROVED → Order may be created. Failure: PRE_FLIGHT APPROVED → market moves → stop invalid → PRE_SUBMISSION REJECTED → no Order.

## Success Criteria

Deterministically: receive TradeIntent → verify eligibility → calculate allowed risk → determine legal quantity → APPROVE or REJECT with reason — using same core Risk in Experiment and OANDA Practice without full institutional Risk platform.
