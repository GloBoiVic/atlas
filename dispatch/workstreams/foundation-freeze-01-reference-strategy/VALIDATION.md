# Validation — Foundation Freeze 01

Status: `PASS`

## Canonical receipt

- ROLE: `VALIDATE`
- STATUS: `PASS`
- OWNED_ARTIFACT: `dispatch/workstreams/foundation-freeze-01-reference-strategy/VALIDATION.md`
- ARTIFACT_UPDATED: `yes` (this file only)
- Branch/CWD verified: `solo/foundation-freeze-01-reference-strategy` / `/Users/vike/Desktop/atlas`
- Repository root verified: `/Users/vike/Desktop/atlas`
- HEAD unchanged by validation.

## Checks

| Result | Command | Exact result |
|---|---|---|
| PASS | `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' TZ=UTC uv run pytest -q backend/tests` | `322 passed, 1 skipped, 4 warnings in 161.49s (0:02:41)` |
| PASS | `ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' uv run alembic upgrade head` | PostgreSQL migration context completed successfully; database was at head (no upgrade operations detected during suite setup) |
| PASS | targeted Strategy/domain/experiments/integration pytest | `54 passed in 10.20s` |
| PASS | `uv run python -m compileall -q backend` | completed without output |
| PASS | `git diff --check` | completed without output |
| PASS | `git diff --name-only -- '*.py' | xargs uv run ruff check` | `All checks passed!` |

The Ruff command above was run against every changed Python application/test file.
An informational repository-wide `uv run ruff check backend` also reported 19
existing formatting/import violations outside the targeted changed-file check; it
was not used as the release gate.

The one pre-existing skip was accepted. Warnings were the Starlette/httpx
deprecation warning and three unregistered `price_analysis` mark warnings.

## Required invariant inspection

- **PASS — legacy restoration:** `git diff aef7187433a6f2c3366220378f5e5dcf133714ff --` is empty for both legacy implementations and both legacy test files. They retain schema 1 semantics and are non-authoritative.
- **PASS — generic default/version boundary:** `StrategyDefinition.state_schema_version` remains `1`; only the corrected `ema_sweep_confirmation_break` definition explicitly declares `state_schema_version=2` and implementation `...v2`.
- **PASS — corrected state quarantine:** the authoritative public seam rejects `StrategyState(schema_version=1)`; no upgrade silently reinterprets schema 1. Legacy schema-1 references are confined to legacy implementations/tests and the intentional rejection coverage.
- **PASS — seed metadata:** corrected reference-strategy integration/configuration seeds use `state_schema_version=2`.
- **PASS — confirmation/evidence:** public assertions cover valid immediate LONG/SHORT confirmation, strict sweep and candle direction, no opposite-reference close requirement, EMA/ATR, proposed stop methodology, trigger/basis, same-candle landmarks, evidence version, and explicit W1–W5/no-wall-clock policy.
- **PASS — nullable expiry/handoff:** model and migrations allow nullable `expiry_time`; corrected `_create_intent` passes `expiry_time=None`; eligibility is ARMED/watch-bar based with observation-before-frontier ordering, not a decision-clock expiry.
- **PASS — W1–W5:** state arms at zero, W1 through W5 are eligible, W6 expires/resets, reset clears stale setup state, and corrected tests cover trigger basis and consumed-bar behavior.

## Stale-assumption search

The stale search found no authoritative use of `AWAITING_CONFIRMATION`, `window_bars`, corrected v1 registration, or wall-clock eligibility. Remaining schema-1/old-window hits are quarantined legacy strategy/test material or the intentional schema-1 rejection test. `ema_sweep_confirmation_break.v2` corrected seeds all specify schema 2.

## Blockers

None. Database-backed validation is complete and the canonical backend suite passes.
