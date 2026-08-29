# Foundation Freeze 06 — Validation

## Status

`PASS` — fresh targeted validation closes original REVIEW findings R-001 through
R-004. The repository-wide web formatting command still reports five
pre-existing untouched files; this remains a non-blocking `TOOLING` baseline
concern below.

## Fresh targeted validation — R-001 through R-004

This validation intentionally did not rerun the full matrix. It read the four
original REVIEW packets, T001/T002/T003 remediation receipts, the current diff,
and frozen `ARCHITECTURE.md`. CWD, repository root, and branch were verified as
`/Users/vike/Desktop/atlas` and
`solo/foundation-freeze-06-strategy-extensibility-proof`. Browser validation was
not required for this scope.

| Original finding | Result | Fresh evidence |
|---|---|---|
| R-001 generic safety boundary | RESOLVED | The focused contract suite passed `116 passed`, including malicious generic `OPEN_LONG` rejection for `exposure_allowed=False` and non-FLAT Position. The shared post-evaluation guard rejects both cases without candidate-specific logic. |
| R-002 active EMA restoration | RESOLVED | EMA contract tests passed, including canonical JSON restoration for each active `reference_time`, `sweep_time`, and `confirmation_time`, byte-preserving timestamp restoration, and round-trip continuation through W1–W5 with W6 expiry. EMA source remains unchanged; raw SHA-256 is `02a285414ec17d514f7d688cc2683eee53ace9e275655c93225f0d9c03621480`. |
| R-003 candidate future methodology timestamp | RESOLVED | Candidate tests passed for future `candidate_started_at` in empty/non-empty contexts, with and without a restored frontier. Equality at the restored frontier and evaluation frontier remains valid and reaches the expected opening decision; rejection occurs before reset/repair. |
| R-004 committed candidate vertical proof | RESOLVED | Isolated PostgreSQL test passed `1 passed` with inline `ATLAS_TEST_DATABASE_URL`. The committed test creates the candidate registration/StrategyVersion and Experiment, asserts immutable parameters, native M15 plus sparse native M1 BID/ASK membership, executes the real V2 runner, and verifies TradeIntent, PRE_FLIGHT/PRE_SUBMISSION Risk, Order, Fill, Position, Trade, accounting/result, generic evidence, pip-derived stop, and result/Trade/price-analysis inspection lineage. |

### Fresh targeted checks

- Focused backend contract/candidate/EMA/domain/configuration/runner/guard
  command: **116 passed**.
- Directly affected result-reader tests: **41 passed**.
- Dedicated PostgreSQL URL, each invocation isolated: candidate vertical
  **1 passed**; existing EMA golden flows **2 passed**; existing API experiment
  evidence **12 passed** with four existing warnings.
- Focused Pyright on changed Strategy/domain application files: **0 errors,
  0 warnings, 0 informations**.
- Focused Ruff, targeted `compileall`, and `git diff --check`: **passed**.
- EMA source diff against base is empty; migration status/diff remains empty.

No original R-001 through R-004 finding remains unresolved. Prior unrelated
passing evidence in this artifact is retained and was not invalidated or
rerun.

### Remaining finding and remediation packet

- **Classification:** `TOOLING / NON-BLOCKING BASELINE`.
- **Finding:** repository-wide `npm run format:check:web` still reports only
  untouched `frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`,
  `frontend/lib/time.ts`, `frontend/tests/time.test.ts`, and
  `tests/e2e/.fixtures.json`.
- **Remediation packet:** maintenance owner should format or explicitly baseline
  those five files in a separate tooling change, then rerun the web formatting
  gate. They are outside this targeted backend validation and were not edited.

## Validation basis

- Role: `VALIDATE`; branch: `solo/foundation-freeze-06-strategy-extensibility-proof`.
- CWD and repository root verified as `/Users/vike/Desktop/atlas`.
- Read `PLAN.md`, frozen `ARCHITECTURE.md`, all four task receipts, the current
  diff/status, relevant architecture documents, source, tests, and API/UI seams;
  then reran the directly dependent EMA/candidate contract, runner, golden,
  persistence, result-reader, frontend, type, and freeze-guard checks.
- Pre-existing/unrelated `.codegraph/`, `frontend/.env.local`, and other
  workstream bookkeeping were preserved and not treated as implementation
  changes.

## Acceptance and invariant matrix

| Area | Result | Evidence |
|---|---|---|
| Explicit registration, catalog, exact provenance | PASS | Candidate registration/provenance tests; guard suite; EMA source is byte-identical to base and raw SHA-256 is `02a285414ec17d514f7d688cc2683eee53ace9e275655c93225f0d9c03621480`. |
| Candidate identity, parameters, strict methodology, pip stops, evidence | PASS | Candidate direct typed and parsed payload contract tests pass; ad-hoc PostgreSQL run produced immediate LONG, stop `1.0960000000`, generic `CANDLE_CONFIRMATION_BREAK_EVIDENCE_V1`, and no pending handoff. |
| Generic parameter/state/evidence/market primitives | PASS | Generic typed evaluation now schema-validates direct candidate values without duplicated candidate bounds; invalid direct values reject. Empty-bar contexts reject a future envelope frontier, while strict duplicate/monotonic and pending consistency checks remain covered. |
| Experiment configuration and PostgreSQL lifecycle | PASS for exercised paths | Isolated persistence `3 passed`, lifecycle `5 passed`, API `12 passed`, golden EMA `2 passed`; inline URL was used only in process environment. Candidate valid snapshot/configuration/execution was exercised through the real runner path; invalid candidate payload rejection is covered by the focused contract/configuration tests. |
| Native data/no-lookahead/sparse execution | PASS | Backend non-integration suite `337 passed, 6 skipped`; clock, coverage, result, and guard tests pass. Candidate run used native persisted M15 and sparse native M1 BID/ASK, with post-frontier execution. |
| Risk → Order → Fill → Position/Trade → result lineage | PASS for exercised paths | Candidate PostgreSQL proof persisted Risk PRE_FLIGHT/PRE_SUBMISSION, Orders, Fills, Trade, account/equity, and result; candidate API detail, price-analysis, and Trade reads returned exact generic evidence. EMA golden flows passed. |
| EMA bytes/fingerprint/regression | PASS | Production compatibility adaptor exposes `StrategyStateEnvelope`, losslessly maps legacy state and the single pending handoff, and keeps EMA source bytes frozen. `cmp`/`git diff --quiet` pass; raw source SHA-256 is `02a285414ec17d514f7d688cc2683eee53ace9e275655c93225f0d9c03621480`; framed archive fingerprint remains `63e50101f73e64f28e4a0f9f0abb7abe3a3181bbf97b8e8841151de70d442156`. Direct EMA/candidate contract, golden, runner, persistence, result, and UI evidence passes. |
| Forbidden seams, legacy candidate, migrations/checkpoints | PASS | `backend/tests/test_foundation_freeze_guards.py`: `5 passed`; no migration diff/status, checkpoint path, checkpoint call, active `ema_sweep_engulfing`, candidate branch in shared seams, or pip conversion in Risk/execution. |
| Schema-driven setup/result/evidence UI | PASS in tests/build; browser unverified | Changed frontend files pass focused Prettier check, frontend typecheck, and focused setup/results/price tests (`17 passed`). Prior full frontend tests (`32 passed`) and production build remain valid. Local Host discovery again reported “Local Host is not running”, so browser interaction remains unavailable. |
| Quality gates | PASS for changed workstream seams; baseline concern retained | Focused Pyright on changed Strategy/domain files is clean (`0 errors`); `git diff --check`, focused Ruff, and compileall pass. Focused frontend formatting/typecheck/tests pass. The repository-wide `npm run format:check:web` still reports only five untouched pre-existing files; see the residual `TOOLING` packet below. |

## Checks run

- `uv run pytest backend/tests --ignore=backend/tests/integration -q` — `337
  passed, 6 skipped`.
- Fresh focused Strategy/domain/candidate/EMA/runner/configuration/guard pass:
  `uv run pytest backend/tests/domain/test_primitives.py
  backend/tests/strategies/test_contract.py
  backend/tests/strategies/test_candle_confirmation_break.py
  backend/tests/strategies/test_ema_sweep_confirmation_break.py
  backend/tests/strategies/test_legacy_strategy_isolation.py
  backend/tests/experiments/test_configuration.py
  backend/tests/experiments/test_runner_diagnostics.py
  backend/tests/test_foundation_freeze_guards.py -q` — `100 passed`.
- Fresh focused Pyright:
  `uv run pyright backend/domain/strategy.py backend/strategies/contract.py
  backend/strategies/production.py backend/strategies/candle_confirmation_break.py`
  — `0 errors, 0 warnings, 0 informations`.
- PostgreSQL, with inline dedicated URL only:
  - `test_strategy_persistence.py` — `3 passed in 3.25s`;
  - `test_golden_flows.py` — `2 passed in 7.98s`;
  - `test_experiment_lifecycle.py` — `5 passed in 16.03s`;
  - `test_api_experiments.py` — `12 passed in 33.39s, 4 existing warnings`;
  - result readers (`test_results.py`, `test_price_analysis_results.py`) —
    `41 passed in 124.66s`;
  - freeze guards — `5 passed in 1.22s`.
- Candidate-specific ad-hoc PostgreSQL vertical proof — completed candidate
  Experiment and verified persisted candidate stop/evidence and full financial
  lineage; API detail, price-analysis, and Trade inspection all returned `200`
  with empty EMA and candidate evidence.
- Fresh inline-URL isolated sequence used
  `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test'`
  for each PostgreSQL/result/guard invocation; the combined invocation remains
  intentionally excluded because module-owned schema teardown is order-sensitive.
- `npm run test:web` — `12 files, 32 passed`; `npm run build:web` — passed;
  `npm run lint:web` — prior `0 errors, 273 warnings` remains valid.
- `npm run typecheck:web` and focused changed-file Prettier check — pass;
  focused UI setup/results/price tests — `17 passed`.
- Focused backend Ruff, `compileall`, and `git diff --check` — pass.
- `npm run format:check:web` — still fails only on untouched existing
  `frontend/app/providers.tsx`, `frontend/components/ui/select.tsx`,
  `frontend/lib/time.ts`, `frontend/tests/time.test.ts`, and
  `tests/e2e/.fixtures.json`; all changed frontend files pass direct Prettier
  check.
- EMA source freeze: `git diff --quiet` and `cmp` against base both pass; raw
  SHA-256 remains `02a285414ec17d514f7d688cc2683eee53ace9e275655c93225f0d9c03621480`.

## Findings and remediation packets

### F-001 — PRODUCT — direct typed candidate parameters bypass schema bounds

- **Remediation status:** `RESOLVED` — fresh direct typed-invalid and
  typed-valid contract/candidate tests pass. The public evaluator applies the
  registered schema generically before implementation evaluation; candidate
  bounds remain declared once in its `ParameterSchema`.

- **Owner task:** `T002-candle-confirmation-strategy` (with the public seam in
  `T001-generic-strategy-contract`).
- **Exact issue:** `CandleConfirmationParameters.__post_init__` checks type and
  finiteness only. `evaluate_strategy` accepts a `StrategyParameterSet` without
  revalidating it against the registered `ParameterSchema`. Reproduction with
  `confirmation_bars=4`, `stop_buffer_pips=0.1`, and `target_r=9` was accepted
  and returned `NO_ACTION` instead of failing closed.
- **Files/seams:** `backend/strategies/candle_confirmation_break.py:82-103`,
  `backend/strategies/contract.py:253-287`.
- **Required fix:** Ensure every public evaluation path either requires the
  validated payload or schema-validates/re-parses the typed value generically
  before evaluation. Do not add EMA/candidate names or duplicate bounds in
  shared code.
- **Invalidated checks:** Invalid-parameter acceptance and public Strategy
  conformance; parsed configuration tests alone are insufficient.
- **Smallest revalidation:** direct typed-invalid and typed-valid contract
  tests, candidate boundary/invalid tests, and focused Strategy/configuration
  suite plus guards.

### F-002 — PRODUCT — EMA compatibility adaptor does not translate state to the frozen envelope

- **Remediation status:** `RESOLVED` — fresh adaptor, EMA state/evidence,
  runner, golden, persistence, and freeze-guard evidence passes. The runner
  boundary is `StrategyStateEnvelope`; legacy EMA DTOs remain private to the
  explicit compatibility codec, including lossless pending handoff mapping.

- **Owner task:** `T001-generic-strategy-contract`.
- **Exact issue:** The production adaptor's `initial_state()` returns legacy
  `StrategyState`, `evaluate()` accepts/delegates legacy state, and the V2
  runner therefore runs EMA with the old DTO rather than an
  `StrategyStateEnvelope`. The frozen architecture explicitly requires the
  adaptor to map legacy EMA state into/from the new envelope while keeping the
  archived EMA source unchanged. `validate_state` also still accepts the
  legacy DTO whenever its schema number matches.
- **Files/seams:** `backend/strategies/production.py:25-72`,
  `backend/strategies/contract.py:201-222,310-320`,
  `backend/experiments/runner.py:430-458`.
- **Required fix:** Keep legacy EMA shapes private inside an explicit
  production compatibility codec/adaptor, expose an envelope to the runner,
  and translate the legacy pending transition to the one normalized handoff.
  Preserve EMA source bytes, state JSON meaning, W1–W6 behavior, and no durable
  checkpoint persistence.
- **Invalidated checks:** Frozen EMA adaptor/state-envelope contract and the
  claim that the runner has fully removed the legacy public state boundary.
- **Smallest revalidation:** envelope/adaptor tests, EMA state/evidence/golden
  tests, runner guard suite, and the isolated PostgreSQL golden flows.

### F-003 — PRODUCT — future envelope frontier is not rejected in an empty-bar context

- **Remediation status:** `RESOLVED` — fresh domain and contract tests reject a
  future `last_evaluated_bar_end` with empty bars, including blocked-exposure
  context, while preserving strict duplicate/monotonic and pending checks.

- **Owner task:** `T001-generic-strategy-contract`.
- **Exact issue:** `StrategyStateEnvelope.__post_init__` only checks UTC and
  `validate_frontier` is called only when advancing. `validate_context` compares
  the state frontier to `context.bars[-1]` only when bars exist. A future
  `last_evaluated_bar_end` can therefore reach an evaluation with no bars (for
  example a blocked-exposure context), contrary to the frozen fail-closed
  future-state invariant.
- **Files/seams:** `backend/domain/strategy.py:1270-1313`,
  `backend/strategies/contract.py:224-250`.
- **Required fix:** Reject an envelope frontier after the supplied evaluation
  time regardless of whether bars are present; retain strict duplicate and
  monotonic checks and reject inconsistent pending metadata without reset.
- **Invalidated checks:** Future-state failure-path coverage and generic state
  safety acceptance.
- **Smallest revalidation:** domain frontier tests, contract tests with empty
  bars and exposure blocked, candidate state round-trip tests, and guard suite.

### F-004 — TOOLING — web formatting gate is red

- **Remediation status:** `RESOLVED for workstream files` — direct Prettier
  check passes for every changed frontend component/test file. The aggregate
  repository command still reports five untouched baseline files; that
  non-blocking residual is packeted separately below.

- **Owner task:** `T003-experiment-and-inspection-proof`.
- **Exact issue:** `npm run format:check:web` reports formatting failures in
  changed `frontend/components/experiments/experiment-setup.tsx` and
  `frontend/components/experiments/shared.ts` (as well as five existing files).
- **Files/seams:** the two changed frontend files above; repository-wide
  Prettier gate.
- **Required fix:** Run the repository formatter for the changed files and
  resolve or separately baseline the remaining pre-existing failures without
  changing behavior.
- **Invalidated checks:** `format:check:web` and the aggregate `check:web` gate.
- **Smallest revalidation:** `npm run format:check:web`.

### F-005 — PRODUCT — strict type contract is non-conforming at new implementations

- **Remediation status:** `RESOLVED` — focused strict Pyright on the changed
  Strategy/domain files returns `0 errors, 0 warnings, 0 informations`; focused
  tests, Ruff, compileall, and diff checks also pass.

- **Owner tasks:** `T001-generic-strategy-contract` and
  `T002-candle-confirmation-strategy`.
- **Exact issue:** Focused strict Pyright reports `48 errors`, including the
  compatibility adaptor and candidate implementations narrowing the
  `Strategy.evaluate` parameter/state types incompatibly with the public
  Protocol, plus untyped restored JSON values in the new domain boundary.
- **Files/seams:** `backend/strategies/contract.py`,
  `backend/strategies/production.py`, `backend/strategies/candle_confirmation_break.py`,
  `backend/domain/strategy.py`.
- **Required fix:** Make implementations conform to the public Protocol via
  typed narrowing/guards and type the mapping restoration boundary. Preserve
  runtime rejection and avoid weakening the contract to `Any`.
- **Invalidated checks:** Strict type quality gate and static conformance claim.
  The pre-existing broad Pyright baseline explains some domain diagnostics but
  does not clear the newly introduced implementation incompatibilities.
- **Smallest revalidation:** focused Pyright on changed Strategy/domain files,
  focused backend tests, and compile/Ruff checks.

### F-006 — TOOLING — combined integration invocation is not a reliable gate

- **Remediation status:** `RESOLVED` — the four PostgreSQL integration modules,
  result readers, and freeze guards pass sequentially with the inline
  dedicated URL. Isolated module execution is the canonical gate; no
  application checks were weakened.

- **Owner task:** `T004-reference-regression-and-validation`.
- **Exact issue:** The combined five-target integration command exceeded the
  900-second timeout after partial progress. Isolated PostgreSQL module runs
  all passed; the receipts also identify shared test-schema teardown as a
  reason not to use the combined persistence/API invocation.
- **Files/seams:** integration fixture/schema lifecycle, especially
  `backend/tests/integration/test_strategy_persistence.py` and related module
  fixtures.
- **Required fix:** Isolate database schema lifecycle per module or document
  isolated commands as the canonical gate; do not weaken application checks.
- **Invalidated checks:** Combined invocation only; isolated results remain
  valid evidence.
- **Smallest revalidation:** rerun the four isolated integration modules (and
  the result-reader suite) against the dedicated database.

### Residual baseline — TOOLING — repository-wide web formatting

- **Status:** `OPEN / NON-BLOCKING`; this is not a changed-workstream-file
  regression and is not critical or important to the frozen Strategy proof.
- **Exact finding:** `npm run format:check:web` reports only the untouched
  existing files `frontend/app/providers.tsx`,
  `frontend/components/ui/select.tsx`, `frontend/lib/time.ts`,
  `frontend/tests/time.test.ts`, and `tests/e2e/.fixtures.json`.
- **Evidence:** Every changed frontend file passes the direct Prettier check;
  frontend typecheck and focused UI tests pass.
- **Remediation packet:** Repository maintenance owner should format or
  explicitly baseline those five files in a separate tooling change, then rerun
  `npm run format:check:web`. VALIDATE did not edit them.

## Concerns / limitations

- Integration emitted one existing Starlette/httpx deprecation warning and
  three existing unregistered `price_analysis` mark warnings.
- Local Host was unavailable, so browser interaction verification was not
  possible; frontend unit tests and production build were used instead.
- The full repository formatting baseline remains the residual `TOOLING`
  concern described above; it does not invalidate the changed-file formatting
  result or the canonical PASS for F-001 through F-006.
- No application, test, fixture, selector, harness, workflow, or artifact
  other than this `VALIDATION.md` was edited during validation.
