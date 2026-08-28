# Atlas North Star

## North Star

Atlas is a trading operating environment for taking an idea through:

**Strategy → Experiment → PAPER → LIVE → Understand → Improve**

Atlas helps a trader turn hypotheses into controlled, explainable, and reproducible trading activity while preserving ownership of capital and product state.

## Atlas-Native Strategy Creation

Long-term, Strategies are created and developed in a constrained Atlas execution environment through an Atlas Strategy SDK.

The environment provides explicitly allowed capabilities, documented Strategy contracts, supported indicators and templates, validation, and semantic feedback.

Strategies remain bounded by Atlas platform rules rather than operating as unrestricted programs.

## Contract-Bound Strategies

Strategies operate only through Atlas contracts.

They may not directly access broker APIs, databases, arbitrary network or filesystem capabilities, subprocesses, or other platform internals.

They may not bypass Atlas Risk, execution, persistence, safety, or audit boundaries.

## Validated Market and Broker Reach

Atlas supports broker, instrument, and timeframe combinations through explicit, validated capabilities.

The current OANDA, EUR/USD, M15 analytical, and M1 execution scope proves the lifecycle; it is not Atlas's permanent boundary.

Expansion occurs one validated capability at a time, without committing the product to specific future markets, brokers, or timeframes.

## One Methodology, Reproducible Lifecycle

A Strategy's immutable methodology must carry unchanged through:

**Experiment → PAPER → LIVE**

Evidence remains reproducible and inspectable across the lifecycle, including methodology, data, assumptions, decisions, execution facts, and outcomes.

Differences between environments must not silently change what the Strategy means.

## The Atlas Agent

The Atlas Agent is an Atlas-aware operator and assistant, not a generic chatbot or an uncontrolled autonomous alpha generator.

It may autonomously:

- inspect and explain Atlas state;
- validate and draft Strategy code;
- run checks that cannot affect capital;
- analyze Experiments and Trades;
- operate other permitted Atlas workflows.

Explicit trader approval is required before the Agent:

- creates or changes capital exposure;
- activates PAPER or LIVE trading;
- changes broker or account credentials;
- changes Risk policy;
- performs destructive or irreversible actions.

## Explainability and Operational Truth

Atlas must always be able to explain:

- what it did;
- why it did it;
- which Strategy methodology and data it used;
- which assumptions and Risk policy applied;
- what actually happened.

Uncertainty, failure, and disagreement must remain visible rather than being converted into false certainty.

## Trader Control

Atlas is local-first and self-hosted in its current direction, while leaving room for optional future controlled services.

The product remains trader-controlled.

The trader controls capital allocation, activation, supervision, and Risk policy. Atlas Risk remains authoritative for individual RiskDecision outcomes under that policy.

## Evolution and Delivery Discipline

Future capabilities may shape today's seams, but they never authorize speculative implementation.

Atlas advances through the smallest trustworthy current vertical slice.

New capability is earned through demonstrated correctness, explicit boundaries, reproducible evidence, and safe operation.
