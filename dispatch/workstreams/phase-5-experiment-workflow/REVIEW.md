# REVIEW — Phase 5 Experiment Workflow (Independent Terminal Review)

## Review — Phase 5: Experiment Workflow
Gate: R1
Spec compliance: PASS
Task quality: PASS
Layer 1 (plan alignment): PASS
Layer 2 (system integrity): PASS
Layer 3 (production readiness): PASS
Findings: 4 Minor (non-blocking) — 2 from this review, 2 carried from VALIDATION.md
Evidence reused: `VALIDATION.md` full-workstream receipt (incl. 219 backend tests + E2E 5/5); `TASK-21.md` canonical E2E 5/5; `TASK-16/18/19.md` correction receipts
Checks rerun: none — the full-workstream `VALIDATION.md` receipt is valid on the current HEAD and unchanged scope; every concern below was verified against on-disk source rather than inferred
Decision: PASS

---

## Scope of this review

Independent terminal review of the Phase 5 Experiment Workflow (`feature/phase-5-experiment-workflow`), per `dispatch/ACTIVE.md`. This replaces the earlier Task-6-scoped `REVIEW.md` as the workstream's terminal gate. I assessed the assigned dimensions against the four authorities — `PLAN.md`, `ARCHITECTURE.md` (including its append-only remediation/UTC/diagnostic blueprints), `VALIDATION.md`, and the relevant `TASK-*.md` receipts — plus on-disk source. No code or Git mutation was performed; this file is the only artifact written.

## Validation-basis check (receipt reuse)

The `VALIDATION.md` full-workstream receipt records: branch `feature/phase-5-experiment-workflow`, HEAD `67c24b714f3c128cfefab0581118638194063de8` (matches current `git rev-parse HEAD` and the Git log top `Implement Phase 4 historical execution`), isolated `atlas_test` PG environment (`postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test`, session `timezone=UTC`, migration `0007_phase_5_metric_contract`), non-UTC host for E2E. The receipt reports **219 passed / 1 skipped** (single skip = external OANDA credential test), the Alembic upgrade/downgrade/upgrade cycle, frontend lint/typecheck/unit/build, generated-OpenAPI contract freshness (byte-identical `frontend/lib/api.generated.ts`), and canonical E2E **5/5** (`--workers=1`), re-confirmed independently against the reused `TASK-21.md` 5/5 receipt. The environment basis, scope, and HEAD are unchanged, so the receipt is reused as valid without rerunning.

## Layer 1 — Plan alignment

The ordered task chain in `PLAN.md` completed through TASK-21, independent full validation (PASS), and this review. The append-only remediation/diagnostic blueprints were followed: Task 12 UTC mismatch → Task 13 UTC session policy → Task 14 lifecycle diagnostic → Task 15 runner-return diagnostic → Task 16 autoflush correction → Task 17 selectors → Task 18 chart repair → Task 19 financing disclosure → Task 20/21 isolated-DB repair. Every remediation was preceded by an approved blueprint section and a mandatory stop before each corrective change, matching the plan's constraint structure.

Scope is bounded: no Phase 6, PAPER/LIVE, comparison, optimization, cancellation, export, background worker, WebSocket, or generic-charting capability entered the change (verified in `backend/experiments/` and `backend/api/experiments.py`). Phase 4 semantics (candle frontiers, execution pricing, Risk, Fill/Position/Trade accounting, stop/target, reproducibility) were not altered; the `autoflush` change and the chart/disclosure repairs are application-composition and read-composition only.

## Layer 2 — System integrity

### UTC / session safety (PASS)
- `backend/persistence/database.py:configure_utc_session_timezone` installs a `SET SESSION TIME ZONE 'UTC'` on both the SQLAlchemy `connect` and `checkout` events, is idempotent per engine, and is wired into `create_database_engine` and `create_session_factory`. The checkout reset closes the pooled-connection timezone-drift path; `pool_pre_ping` is retained.
- Adoption is complete across the production, CLI, runtime, online-Alembic (`migrations/env.py:39`), E2E-seed, and integration-test engine paths — matching the blueprint's required inventory. The canonical context owner `context/architecture/database.md` (§Time) carries the exact approved UTC-session paragraph (line 35); no alternate rule exists elsewhere.
- Naive-vs-aware normalization in `version_to_domain`/`_utc` and RFC3339 `Z` serialization are covered by the Task-6-validated integration tokens.
- **[Minor — doc drift]** `create_session_factory` now uses `autoflush=True` (Task 16), whereas the ARCHITECTURE.md UTC blueprint (line 491) documented `autoflush=False` as "unchanged". The change was a separately approved, evidence-proven correction (the API session failed to observe pending entry facts under `autoflush=False`, while the direct integration path already used `autoflush=True`); the blueprint text was not updated to record it. Runtime/safety impact is nil (single-user, synchronous, aligns API composition with the runner path; 219 tests + E2E 5/5 pass). Non-blocking; recommend reconciling the blueprint/comment wording in a follow-up.

### Diagnostics leakage (PASS)
- Three diagnostic record types exist: `Phase4ValueErrorDiagnostic`, `Phase4RunnerComparisonDiagnostic` (both in `runner.py`), and `ExperimentLifecycleDiagnostic` (`lifecycle.py`). All are closed contracts (fixed key sets), use allow-listed reason codes / exception-class names / SQLSTATE / timezone / revision validation, and never serialize exception text, credentials, SQL, paths, UUIDs, or raw values.
- Hostile-input and raising-sink tests (`test_runner_diagnostics.py`, `test_lifecycle_diagnostics.py`) prove unknown text maps to `UNCLASSIFIED_VALUE_ERROR`/`UNCLASSIFIED_EXCEPTION` and that sink failure cannot alter the sanitized result.
- Production `create_app` (`backend/api/app.py:33-34,43-44,58-60`) defaults both diagnostic sinks to `None`. The E2E adapter `backend/tests/e2e_app.py` is the only emitter, is guarded to refuse a non-`*_test` database, and `playwright.config.ts` selects it only when the explicit `ATLAS_E2E_*_DIAGNOSTIC=1` flags are set; the canonical configuration defaults to production `create_app`. No diagnostic data crosses an Experiment row, API response, OpenAPI, browser payload, or normal log.

### Chart / financing (PASS)
- `results.py:_chart` aggregates immutable DatasetSnapshot membership into canonical M15 MID bars, computes EMA 100 over progressively available full history before window selection (so displayed EMA values are canonical), reads rationale field markers via `.items()` (Task 18 fix, tolerant of pair-sequence fixtures), bounds the context at 500 candles with an omitted-range disclosure, and annotates strategy/entry/exit. The chart test verifies snapshot-source usage, bounded output, EMA presence, annotation set, and omitted range.
- Trade detail now exposes `financing_disclosure` from the immutable `simulation_config` (`results.py:203-207`); the frontend renders it, and the E2E asserts `FINANCING EXCLUDED` on Trade detail. Tests cover the disclosure at both backend and frontend layers.
- **[Minor — blueprint drift, unverified requirement]** ARCHITECTURE.md line 91 states chart context preserves "at least EMA period plus 20 preceding bars" of setup context. The implementation selects `range(center-21, center+2)` per marker, i.e. ~22 candles per marker, far fewer than EMA period (100) + 20. EMA values remain correct (computed over full history), so this is presentation-only and does not mislead; but the explicit blueprint requirement is not literally met and no test asserts it (the chart test checks `<= 500`, EMA present, omitted range, annotations). Non-blocking; recommend either widening the per-marker window where it fits under 500 or reconciling the blueprint wording.

## Layer 3 — Production readiness

### E2E (PASS)
- Reused the `TASK-21.md` 5/5 receipt, independently re-confirmed in `VALIDATION.md`: configure→validate→create→run→observe→completed result→Trade detail (including the financing disclosure and a real Trade chart), invalid-coverage prevention, failed-Experiment-without-partial-results, zero-Trade completion, and foundation. Selectors are disambiguated (`header .status` filter), and the retry-safe terminal `POST /run` idempotency is exercised in the primary scenario. No OANDA credentials, network market data, current time/session, or special app factory are required.

### Tests (PASS)
- Reused the full backend suite receipt (219 passed / 1 skipped, the OANDA-credential skip being expected), migration cycle, frontend gates, and contract-freshness checks. Focused suites for diagnostics, chart, financing, lifecycle stage-ordering, UTC policy, and valid-run baseline-vs-candidate comparisons are present and green.

## Independent findings

1. **[Minor — non-blocking]** `autoflush=True` in `create_session_factory` deviates from the ARCHITECTURE.md UTC blueprint's documented `autoflush=False`; it is an approved, evidence-proven, bounded correction (Task 16) with no safety impact, but the blueprint text was not updated to reflect it.
2. **[Minor — non-blocking]** Chart setup-context window does not literally meet the blueprint's "EMA period + 20 preceding bars" requirement and is unverified by any test; EMA values are canonical so this is presentation-only.
3. **[Minor — carried from VALIDATION]** `pyright backend` (strict) is non-clean (1132 errors; 757 at Phase 4 baseline) — a pre-existing project-wide gate, not a Phase 5 regression; no receipt claimed it.
4. **[Minor — carried from VALIDATION]** `format:check:web` flags `experiment-workflow.tsx` (one-line Prettier indent) and `tests/e2e/.fixtures.json` (intended generated compact format).

None is Critical or Important. No blocking finding, blocker, or required evidence remains.

## Verdict

**PASS.** The Phase 5 Experiment Workflow meets its plan, preserves the immutable-Experiment/Phase-4/reproducibility/no-lookahead invariants, enforces the UTC session policy across all application and migration PG paths, keeps all diagnostic instrumentation default-off and leak-free, corrects the chart/disclosure compositions, and passes the full backend, migration, frontend, contract-freshness, and canonical E2E gates (5/5). The four Minor findings are non-blocking and do not require re-work before closure.

Terminal eligibility: the requested R1 gate passes with no Critical or Important finding. Closure may proceed per the review skill's terminal protocol (documenter append to `COMPLETED.md`, `/remember save`, clear `ACTIVE.md`).
