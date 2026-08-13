# Strategy Management

## Purpose

Lets Atlas discover, validate, version, and inspect Python trading Strategies. The trader writes Strategy code outside Atlas — Atlas is not initially a code editor.

## Core Model

Strategy (long-lived methodology identity) → StrategyVersion (immutable executable snapshot). Canonical semantics: [Domain Model](../architecture/domain-model.md).

## Strategy Discovery / Registration

Discover Strategies through one explicit local registration mechanism. Each discovered Strategy must expose the public Strategy contract (see [Strategy Contract](../architecture/strategy-contract.md)). Do not build generic plugin marketplace or dynamic extension framework. Registration determines: identity, implementation source, parameter schema, primary/additional timeframes, warm-up, capabilities, state schema/version.

## Strategy Validation

Before creating a usable StrategyVersion, validate: contract compliance, parameter schema, timeframes, warm-up, serializable state, capability declarations, source fingerprint generation. Invalid Strategies → actionable errors, not unrelated crashes.

## Strategy UI

**List**: name, description, latest version, Experiment count, Deployment status. No raw UUIDs. **Detail**: Overview, Versions, Experiments, Deployments — main lifecycle workspace for one methodology. No source code unless future feature requires it.

## StrategyVersion Creation

New version when executable behavior changes (entry/exit/indicator/state-machine/methodology source). Once created: immutable. Parameter changes (EMA Period 100→150, ATR Buffer 0.5→0.75) do not create a new version — belong to Experiment/Deployment config.

## Source Fingerprinting

Fingerprint executable Strategy source unit. Answers: What exact code produced this Experiment/Deployment? Optional git metadata. Do not use git commit as only version proof. Source changed → existing version unchanged → new may be created. No silent mutation.

## Source Scope / Parameter Schema / Timeframe / Capabilities

v1: keep methodology source self-contained. Typed parameters: integer, decimal, boolean, enum/string. Definitions include name, label, type, default, min/max, allowed values, description. No UI code in Strategy definitions. Primary timeframe (15m for reference) plus optional context timeframes. Warm-up requirement declared. Capability declarations (LONG, SHORT, STOP_LOSS, TAKE_PROFIT) checked against Instrument/TradingAccount before Deployment.

## Strategy State / Reference Strategy

Atlas persists minimum deterministic state across runtime restart. State semantics: [Strategy Contract](../architecture/strategy-contract.md). No raw internal state prominently in UI. Reference Strategy (EMA Sweep Engulfing) uses only the public contract. No strategy-specific handling in generic infrastructure.

## Acceptance Flow

Write externally → register/discover → validate → create Strategy → create immutable StrategyVersion → ready for Experiment.

## Version Detail / Archival

Version detail: label, created timestamp, source fingerprint, optional git ref, parameter schema, timeframe/warm-up/capability, linked Experiments/Deployments. Prefer archival over deletion once historical provenance exists — versions referenced by Experiment/Deployment/Trade remain available.

## Non-Goals

No browser-based Strategy editor, marketplace, package installer, plugin system, cloud registry, code generation, optimization, multi-user sharing.

## Required Tests

Valid discovery, invalid rejection, parameter schema validation, source fingerprint stability, source change → new version path, existing version immutable, parameter change → no new version, timeframe validation, warm-up declaration, capability validation, state serialization compatibility, reference Strategy uses public contract.

## Success Criteria

Trader can register Python Strategy → Atlas validates → immutable StrategyVersion exists → inspect requirements/parameters → select for Experiment — without Atlas containing methodology-specific infrastructure.
