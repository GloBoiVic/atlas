# Foundation Freeze 06 — Review

## Status

`PASS` — original findings R-001 through R-004 are resolved. No unresolved
`CRITICAL` or `IMPORTANT` finding remains.

## Review basis

- **Role:** `REVIEW`
- **Workstream:** `foundation-freeze-06-strategy-extensibility-proof`
- **Branch/CWD:** `solo/foundation-freeze-06-strategy-extensibility-proof` /
  `/Users/vike/Desktop/atlas`
- Fresh targeted review read the original findings, the remediation diffs,
  frozen `ARCHITECTURE.md`, owning T001/T002/T003 receipts, and fresh targeted
  `VALIDATION.md` evidence. It did not rerun the full workstream matrix.
- Current status contains the expected BUILD changes plus workstream
  bookkeeping. Pre-existing `.codegraph/` and `frontend/.env.local` were not
  changed or treated as implementation work; the latter contains only the
  local API URL.

## Findings

### R-001 — PRODUCT / IMPORTANT — RESOLVED — public Strategy evaluation did not enforce the frozen exposure safety boundary

- **Original issue:** `evaluate_strategy()` validated the input context and the
  returned state, but never rejects an opening `StrategyDecision` when
  `context.exposure_allowed` is false or `context.position` is non-FLAT. A
  deliberately unsafe generic implementation was accepted by the current
  public seam and returned `OPEN_LONG` under `exposure_allowed=False`.
  Registered EMA and Candle implementations currently self-guard, but that
  does not satisfy the frozen Atlas-owned safety invariant for a generic
  Strategy boundary.
- **Owning BUILD task:** `T001-generic-strategy-contract`.
- **Affected files/seams:** `backend/strategies/contract.py:274-327`,
  `backend/domain/strategy.py:1327-1405`, and the runner's shared
  `evaluate_strategy()` call sites in `backend/experiments/runner.py`.
- **Required fix:** Add a generic post-evaluation guard (or equivalent
  fail-closed contract rule) rejecting any opening action under blocked
  exposure or a non-FLAT Position. Do not rely on candidate-specific guards or
  silently reset state; preserve the existing EMA and candidate behavior.
- **Invalidated checks:** public Strategy conformance, generic safety, and the
  claim that the Atlas-owned envelope prevents unsafe opening decisions.
- **Smallest revalidation/rereview:** add blocked/non-FLAT malicious generic
  Strategy tests, rerun the focused domain/contract/candidate/EMA/runner suite
  and freeze guards, then review only the changed contract seam.

- **Resolution evidence:** `evaluate_strategy()` now applies one shared
  post-evaluation guard for both blocked exposure and non-FLAT Position. The
  malicious generic tests cover both paths; the fresh targeted validation
  receipt reports the focused contract suite at `116 passed`, and the reviewer
  reran the contract/candidate/EMA/freeze-guard subset at `39 passed`.

### R-002 — REGRESSION / IMPORTANT — RESOLVED — active EMA envelope JSON could not be restored by the compatibility adaptor

- **Original issue:** `StrategyStatePayloadDocument.to_json()` serialized datetime
  payload values to strings, while `from_json()` restores them as plain
  strings. `EmaSweepConfirmationBreakCompatibilityAdaptor._optional_timestamp()`
  accepts only `datetime`. An active EMA envelope containing
  `reference_time`, `sweep_time`, or `confirmation_time` therefore fails when
  restored from its own canonical JSON. Independent reproduction produced
  `roundtrip_equal=False` and `StateError: EMA state payload contains invalid
  values`. The current tests cover initial state and live transitions, not an
  active EMA envelope restore.
- **Owning BUILD task:** `T001-generic-strategy-contract`.
- **Affected files/seams:** `backend/domain/strategy.py:1096-1198`,
  `backend/strategies/production.py:87-168`, and the EMA envelope/adaptor
  restoration contract.
- **Required fix:** Make the explicit EMA compatibility codec consume its
  canonical wire timestamps (normalizing them to validated UTC datetimes) and
  preserve deterministic canonical serialization and legacy state meaning.
  Do not alter the archived EMA source or add checkpoint persistence.
- **Invalidated checks:** EMA envelope round-trip/restoration, restart/state
  safety evidence, and the T001 claim that legacy state is losslessly mapped
  through the new public envelope.
- **Smallest revalidation/rereview:** active EMA state with all timestamp
  combinations plus pending W1–W5/W6 round-trip/continuation tests; rerun EMA
  contract/golden tests, focused Pyright, and guards; review only the codec and
  dependent runner seam.

- **Resolution evidence:** the explicit production compatibility codec now
  parses canonical wire timestamps and normalizes them to validated UTC
  datetimes without changing the EMA source module. Fresh tests restore active
  `reference_time`, `sweep_time`, and `confirmation_time`, then continue W1–W5
  and expire at W6. Validation records the unchanged EMA source SHA-256 and
  `0` focused Pyright diagnostics; the reviewer reran the affected EMA subset.

### R-003 — PRODUCT / IMPORTANT — RESOLVED — candidate accepted a future methodology state timestamp

- **Original issue:** `CandleConfirmationBreakStrategy._state_values()` verified
  that `candidate_started_at` is UTC, but does not compare it with the Atlas
  frontier or evaluation time. A state with frontier `2026-01-01T10:15Z` and
  `candidate_started_at=2099-01-01T00:00Z` was accepted and produced an
  `OPEN_LONG` on the next bar. This violates the frozen invalid/future-state
  fail-closed rule; the generic envelope only protects its Atlas frontier, not
  the candidate payload's methodology timestamp.
- **Owning BUILD task:** `T002-candle-confirmation-strategy`.
- **Affected files/seams:** `backend/strategies/candle_confirmation_break.py:133-178`
  and the public candidate evaluation path in
  `backend/strategies/contract.py:274-327`.
- **Required fix:** Reject a non-null candidate start timestamp later than the
  restored frontier and later than the supplied evaluation frontier (including
  a state with no prior frontier). Keep the candidate payload bounded and do
  not repair/reset malformed state.
- **Invalidated checks:** candidate state safety, invalid-state fail-closed
  acceptance, and the frozen deterministic continuation claim.
- **Smallest revalidation/rereview:** add future-timestamp tests for empty and
  non-empty contexts plus valid boundary equality; rerun candidate contract,
  state round-trip, focused contract, and guard suites.

- **Resolution evidence:** `_state_values()` now rejects a non-null
  `candidate_started_at` later than both the restored Atlas frontier and the
  supplied evaluation frontier, before any reset or decision. Fresh tests cover
  empty/non-empty contexts, with/without a prior frontier, and equality at each
  valid boundary. The targeted validation receipt reports these tests and the
  guard suite passing.

### R-004 — TOOLING / IMPORTANT — RESOLVED — required candidate V2 vertical proof was not committed as a regression test

- **Original issue:** The T003 receipt and VALIDATION claim a candidate
  PostgreSQL vertical proof, but it was an ad-hoc run. The committed
  integration tests only exercise the EMA seed/registry path; repository
  search finds no candidate integration test that creates and runs a candidate
  Experiment through the real V2 runner. Consequently CI does not prove the
  candidate's immutable parameter snapshot, native M15 plus sparse native M1
  handoff, immediate post-frontier entry, Risk PRE_FLIGHT/PRE_SUBMISSION,
  Order/Fill/Position/Trade/accounting/result lineage, or persisted candidate
  evidence/stop.
- **Owning BUILD task:** `T003-experiment-and-inspection-proof`.
- **Affected files/seams:** candidate integration fixture/seed and the
  `backend/tests/integration` coverage of
  `backend/experiments/runner.py`, persistence, result readers, and API
  inspection. No application seam is being accused by this finding; the
  acceptance evidence is incomplete.
- **Required fix:** Commit the smallest deterministic PostgreSQL-backed test
  using the candidate StrategyVersion and native V2 snapshot that asserts the
  full shared financial/result lineage, post-frontier BID/ASK immediate fill,
  exact generic evidence and pip-derived stop, plus a candidate zero-trade or
  invalid/fail-closed case as applicable. Keep the runner/Risk/execution
  identity-neutral and do not add fixtures that bypass the real path.
- **Invalidated checks:** T003 candidate Experiment/execution/inspection
  acceptance and the architecture's candidate vertical test matrix. The
  ad-hoc receipt evidence remains useful diagnosis but is not a repeatable
  repository check.
- **Smallest revalidation/rereview:** run the new isolated PostgreSQL module
  against the dedicated test URL, candidate result/API tests, existing EMA
  golden flows, and freeze guards; review the new test and the exercised seams.

- **Resolution evidence:** `backend/tests/integration/test_candidate_vertical_flow.py`
  is now present as a repository regression test in the workstream diff. It uses the explicit
  production registration, persists the candidate StrategyVersion and
  Experiment, seeds native M15 MID plus sparse native M1 BID/ASK data, runs the
  real V2 path, and asserts TradeIntent, both Risk phases, Order/Fill,
  Position/Trade, accounting/result, generic evidence, pip-derived stop, and
  result/Trade/price-analysis inspection lineage. The isolated PostgreSQL run
  passed `1 passed` both in the fresh validation receipt and in the reviewer
  rerun.

## Verified passes and constraints

- Fresh targeted validation reports the focused backend contract/candidate/
  EMA/configuration/runner/guard suite at `116 passed`; reviewer rerun of the
  directly affected contract/candidate/EMA/guard subset: `39 passed`.
- Independent focused frontend typecheck and setup/results/price suite:
  `17 passed`.
- Changed-backend Ruff: passed; `git diff --check`: passed.
- EMA source file has no diff from base SHA; migration status/diff is empty;
  freeze guards pass. No checkpoint artifact or persistence path was found.
- Repository-wide web formatting remains red only in the five untouched files
  documented by VALIDATION.md (`providers.tsx`, `select.tsx`, `time.ts`,
  `time.test.ts`, `.fixtures.json`); this is a pre-existing non-blocking
  TOOLING baseline concern, not a workstream finding.
- No unrelated application/test files were identified in the current diff;
  pre-existing dirty files were preserved. The remediation diff stays within
  the frozen generic contract, explicit EMA composition codec, candidate
  Strategy, and candidate proof test seams.

## Frozen-boundary review

- Shared orchestration remains identity-neutral: the freeze guards pass and no
  candidate-specific branch appears in runner, Risk, execution, market-data,
  snapshot, or result interpretation seams.
- EMA source bytes and provenance remain unchanged; no migration, checkpoint
  table/path/persistence call, or other durable mid-Experiment state was added.
- The candidate uses the existing registration/provenance, native V2 data,
  immediate-entry, Risk, execution, accounting, and inspection seams. No new
  capability, broker, instrument, plugin/discovery mechanism, or scope
  expansion appeared.

## Review decision

`PASS`. R-001, R-002, R-003, and R-004 are each `RESOLVED`; no new blocker was
found and no further remediation cycle is initiated. The only recorded
limitations are the pre-existing repository-wide web-formatting baseline and
unavailable Local Host browser validation, both covered by fresh
`VALIDATION.md` evidence and non-blocking for this targeted backend proof. No
application code, tests, fixtures, selectors, harness, workflow, or artifact
other than this `REVIEW.md` was edited by REVIEW.
