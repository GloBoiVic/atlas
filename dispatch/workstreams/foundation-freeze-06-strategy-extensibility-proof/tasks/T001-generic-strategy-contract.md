# T001 — Generic Strategy Contract

## Assignment

- **Status:** `DONE` — developer-approved narrow remediation for R-001 and
  R-002 completed.
- **Owner:** BUILD
- **Workstream:** `foundation-freeze-06-strategy-extensibility-proof`
- **Branch:** `solo/foundation-freeze-06-strategy-extensibility-proof`
- **Dependencies:** none

Implement the smallest constrained generic Strategy boundary required by the
frozen `ARCHITECTURE.md`. Preserve the EMA implementation, serialized facts,
source provenance, and financial/execution semantics through an explicit
compatibility adaptor.

## Required scope

- Add immutable exact-schema `ValidatedParameterPayload` backed by the frozen
  primitive, size, canonical-serialization, default, bounds, allowed-values,
  nullability, and exact-key rules.
- Add the Strategy-owned typed parameter parser seam and keep the legacy EMA
  DTO compatibility-only; configuration and runner must no longer construct or
  name EMA fields.
- Add Atlas-owned `StrategyStateEnvelope`, bounded typed strategy payload codec,
  and normalized `PendingEntryHandoff` with the frozen frontier/safety rules.
  State remains in memory for historical runs; do not add persistence, migration,
  checkpoint table, or checkpoint file.
- Add bounded immutable generic `StrategyEvidence` and transport it without
  interpreting candidate fields, while preserving the existing EMA SetupFacts
  branch byte-for-byte in meaning.
- Add capability-neutral immutable `MarketSpecification(instrument, pip_size)`
  and wire the existing validated EUR/USD capability resolver to StrategyContext.
  Do not add instruments, providers, or a generalized market SDK.
- Update only the shared contract plumbing and directly affected tests. Do not
  implement Candle Confirmation Break in this task.

## Frozen constraints

Read `ARCHITECTURE.md` §§ Constrained generic contract, Compatibility and
persistence rules, Invariants and failure behavior, and Required test matrix
before editing. No candidate identity branches in shared runner/Risk/execution.
No durable mid-Experiment state. If durable checkpoint state appears necessary,
stop and report `BLOCKED` for developer review.

## Required checks

Run focused contract/EMA compatibility tests and relevant type/lint checks. Add
deterministic tests for valid, invalid, boundary, oversized, future/duplicate
frontier, state round-trip, evidence, and market-spec behavior as applicable.

## Completion receipt

Before returning, update this file with `DONE`, files changed, checks/evidence,
and findings/concerns. Do not edit PLAN, ACTIVE, ARCHITECTURE, VALIDATION, or
REVIEW.

## Completion receipt

- **Status:** `DONE`
- **Files changed:**
  - `backend/domain/__init__.py`
  - `backend/domain/strategy.py`
  - `backend/experiments/configuration.py`
  - `backend/experiments/runner.py`
  - `backend/integrations/oanda/capabilities.py`
  - `backend/strategies/__init__.py`
  - `backend/strategies/contract.py`
  - `backend/strategies/ema_sweep_confirmation_break.py`
  - `backend/tests/domain/test_primitives.py`
  - `backend/tests/experiments/test_runner_diagnostics.py`
  - `backend/tests/strategies/test_contract.py`
- **Checks/evidence:** focused contract/EMA/regression/runner tests passed (`83 passed`); broader non-integration suite passed (`273 passed, 4 skipped`); Ruff, `compileall`, and `git diff --check` passed. Generic exact-schema parameters, bounded state/evidence, frontier guards, normalized pending handoff, and resolver-backed market specification are covered by deterministic tests.
- **Findings/concerns:** no durable checkpoint persistence, migration, or checkpoint path was added. Strict Pyright remains non-clean in this pre-existing codebase (45 errors in the focused domain/strategy invocation; the broader invocation reported 944), so it was not used as a passing gate. Existing integration tests requiring unavailable external database infrastructure were not treated as T001 failures; pre-existing unrelated untracked files and `dispatch/ACTIVE.md` changes were preserved.

## Remediation packet — VALIDATE/REVIEW return 1

- **Classification:** `PRODUCT`
- **Exact issue:** T001 added `initial_state` and `parse_parameters` directly to
  `backend/strategies/ema_sweep_confirmation_break.py`, changing the registered
  EMA source archive/fingerprint from the frozen base value
  `63e50101f73e64f28e4a0f9f0abb7abe3a3181bbf97b8e8841151de70d442156` to
  `f03e815ce1a6dd7fa465f16582bb92955b7c93fa1bd167de2967d2873ddf0bf2`.
  This violates the frozen requirement that the original EMA provenance,
  source bytes, and persisted historical meaning remain unchanged.
- **Owning BUILD task:** `T001-generic-strategy-contract`
- **Affected files/seams:** `backend/strategies/ema_sweep_confirmation_break.py`,
  production registry composition, and the generic Strategy factory/parser
  seam that currently expects methods on the concrete EMA class.
- **Required fix:** restore the EMA module byte-for-byte to the base SHA and
  provide the new generic parser/initial-state behavior through the explicit
  production composition compatibility adaptor (or another frozen-boundary
  contract seam that does not alter the archived EMA source). Preserve exact
  EMA behavior and source fingerprint; do not add persistence or architecture
  scope.
- **Checks invalidated:** T001 provenance/fingerprint evidence and T004's
  reference regression/guard completion. Existing generic/candidate checks may
  remain valid unless the adaptor change affects their call path.
- **Smallest revalidation:** rerun the exact EMA source fingerprint/provenance,
  EMA contract/golden/state/evidence tests and the T001 focused contract suite;
  then rerun T004's guard suite. No full validation rerun is required unless the
  remediation changes a broad authority seam.

## Remediation completion receipt

- **Status:** `DONE`
- **Files changed:**
  - `backend/strategies/ema_sweep_confirmation_break.py` — restored byte-for-byte to base SHA `50c5e18b27d2d652c807f4ca3068ca66cd664687`; source SHA-256 matches base (`02a285414ec17d514f7d688cc2683eee53ace9e275655c93225f0d9c03621480`).
  - `backend/strategies/production.py` — added the explicit EMA compatibility adaptor for generic parameter parsing and initial state, delegating evaluation to the frozen implementation.
  - `backend/tests/strategies/test_legacy_strategy_isolation.py` — updated the production composition assertion for the adaptor.
  - `backend/tests/integration/test_golden_flows.py` — routed the golden registry helper through the adaptor.
- **Checks/evidence:** single-file EMA archive fingerprint is exactly `63e50101f73e64f28e4a0f9f0abb7abe3a3181bbf97b8e8841151de70d442156`; `uv run pytest backend/tests/strategies -q` passed (`36 passed`); T001 focused suite passed (`86 passed`); T004 guard suite passed (`5 passed`); Ruff, compileall, and `git diff --check` passed. Golden flow tests were collected and skipped (`2 skipped`) because `ATLAS_TEST_DATABASE_URL` was unset.
- **Findings/concerns:** no EMA source bytes, methodology, persisted facts, database schema, checkpoint path, or Git history were changed. The registry's explicit source allow-list remains unchanged; the adaptor is production composition plumbing only.

## Remediation completion receipt — VALIDATE return 1 (F-002, F-003, F-005)

- **Status:** `DONE`
- **Files changed:**
  - `backend/domain/strategy.py` — future-frontier validation for empty-bar contexts and typed restoration boundaries.
  - `backend/strategies/contract.py` — envelope-only public state boundary, typed parser/result guards, and strict state-result validation.
  - `backend/strategies/production.py` — explicit EMA compatibility codec/adaptor mapping legacy state and pending handoff to/from `StrategyStateEnvelope`.
  - `backend/strategies/candle_confirmation_break.py` — public Protocol-conforming typed narrowing without behavior changes.
  - `backend/experiments/runner.py` — envelope state initialization and mechanical pending-handoff synchronization without persistence.
  - `backend/tests/strategies/test_contract.py`
  - `backend/tests/strategies/test_legacy_strategy_isolation.py`
  - `backend/tests/strategies/test_ema_sweep_confirmation_break.py`
- **Checks/evidence:** focused domain/contract/adaptor/candidate/runner/guard suite passed (`92 passed`); Strategy suite passed (`39 passed`); focused Pyright on changed Strategy/domain files passed (`0 errors`); focused Ruff, compileall, and `git diff --check` passed. Empty-bar future frontier and incompatible legacy public state are covered. EMA source SHA-256 remains `02a285414ec17d514f7d688cc2683eee53ace9e275655c93225f0d9c03621480`, and `git diff --quiet 50c5e18b27d2d652c807f4ca3068ca66cd664687 -- backend/strategies/ema_sweep_confirmation_break.py` passed.
- **Findings/concerns:** no EMA source bytes, methodology, persisted facts, database schema, checkpoint path, or Git history were changed. The runner and adaptor retain state only in memory; pre-existing unrelated worktree changes were preserved. The broad non-integration run exceeded the local 120-second command limit after partial progress; required focused checks passed.

## Remediation packet — VALIDATE return 1 (F-002, F-003, F-005)

- **Classification:** `PRODUCT` as recorded by validation.
- **Exact issues:** The EMA production adaptor still exposes legacy
  `StrategyState` to the runner instead of translating to/from the frozen
  `StrategyStateEnvelope`; `validate_state` still accepts the legacy DTO at the
  public boundary. A future envelope frontier can pass when the context has no
  bars. Focused strict Pyright also reports new implementation/protocol and
  restored-mapping typing errors in the changed contract seams.
- **Owning task:** `T001-generic-strategy-contract`.
- **Affected files/seams:** `backend/strategies/production.py`,
  `backend/strategies/contract.py`, `backend/domain/strategy.py`, and runner
  state handoff only as directly required by the adaptor.
- **Required fix:** Keep legacy EMA DTOs private inside the explicit production
  compatibility codec; expose `StrategyStateEnvelope` to the runner and map the
  legacy state, pending transition, and state meaning losslessly. Reject future
  frontiers even with empty bars and reject incompatible legacy public state.
  Resolve introduced strict typing without `Any`, candidate names, persistence,
  or architecture changes.
- **Invalidated checks:** EMA envelope/adaptor contract, future-state safety,
  strict static conformance, and dependent T001/T002 behavior claims.
- **Smallest revalidation:** focused contract/domain/adaptor tests, direct empty-
  context future-frontier test, focused Pyright on changed Strategy/domain files,
  EMA state/evidence/golden tests, and guard suite.

## Review return 2 disposition — automatic cycling stopped

- **Classification:** `PRODUCT BLOCKER`
- **Exact issues:** The public evaluator still accepts an unsafe opening decision
  from a generic implementation when exposure is blocked or Position is non-FLAT
  (R-001). Active EMA envelope timestamps do not restore from canonical JSON
  through the explicit adaptor (R-002).
- **Owning task:** `T001-generic-strategy-contract`.
- **Affected files/seams:** `backend/strategies/contract.py`,
  `backend/domain/strategy.py`, `backend/strategies/production.py`, and
  directly dependent runner state handoff.
- **Smallest next action after approval:** add the Atlas-owned post-evaluation
  opening safety guard and typed UTC timestamp normalization in the EMA codec;
  rerun blocked/non-FLAT malicious Strategy tests, active EMA envelope
  round-trip/continuation, focused Strategy/domain/Pyright suites, and guards.

## Remediation completion receipt — REVIEW return 2 (R-001, R-002)

- **Status:** `DONE`
- **Files changed:**
  - `backend/strategies/contract.py` — added the generic post-evaluation guard
    rejecting opening decisions when exposure is blocked or Position is not FLAT.
  - `backend/strategies/production.py` — normalized canonical EMA wire
    timestamps to validated UTC datetimes inside the explicit compatibility
    adaptor only.
  - `backend/tests/strategies/test_contract.py` — added malicious generic
    blocked-exposure and non-FLAT opening tests.
  - `backend/tests/strategies/test_ema_sweep_confirmation_break.py` — added
    active timestamp round-trip/continuation coverage and W1–W5/W6 pending
    continuation coverage across canonical state restoration.
- **Checks/evidence:** focused domain/contract/adaptor/candidate/runner/guard
  suite passed (`99 passed`); focused Strategy regression suite passed (`22
  passed`); `ruff check` passed; focused Pyright on changed application Strategy
  files passed (`0 errors`); compileall and `git diff --check` passed; EMA
  source is unchanged from base SHA; golden-flow tests were collected and
  skipped (`2 skipped`) because `ATLAS_TEST_DATABASE_URL` is unset.
- **Findings/concerns:** no EMA source bytes, methodology, persisted state,
  migration, checkpoint path, or Git history changed. The repository's strict
  test-file Pyright invocation retains pre-existing unknown/legacy-union errors;
  changed application files are clean. No unrelated worktree changes were
  modified.
