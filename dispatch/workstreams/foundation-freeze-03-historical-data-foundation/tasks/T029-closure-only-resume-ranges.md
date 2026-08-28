# T029 — Closure-only resume ranges

Status: `DONE`

The stopped `atlas_test` run durably contains 262 successful M15 and 262 successful
M1 windows. Its legacy M1 windows leave 261 inter-window holes, and inspection shows
the sampled holes contain zero expected open-session minutes. The current V2 resume
planner would treat those acquisition-union holes as uncovered provider work.

Make the narrow correctness/performance fix required by the developer request: a
closure-only remainder is excluded from provider acquisition, while a missing range
containing any expected observation may continue to bridge closures and is split only
at the configured OANDA bound. Do not change validation, sparse observation semantics,
successful-window union, fingerprinting, or other performance stages.

Add deterministic tests for closure-only holes, closure-bridging missing spans, and
half-open/boundary behavior. Do not start OANDA or a full-year run. Update this receipt
with implementation and focused-check evidence.

## Receipt

ROLE: BUILD
STATUS: DONE
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T029-closure-only-resume-ranges.md`
FILES CHANGED: `backend/market_data/ingestion.py`; `backend/tests/market_data/test_freeze03_regressions.py`; this receipt
CHECKS / EVIDENCE: `_coalesce_expected_ranges` now drops closure-only spans, preserves one calendar range across closures, and splits at 4,000 M1 / 60,000 M15 minutes. Focused Freeze 03 regressions: 14 passed. Relevant market-data/load suite: 81 passed, 2 skipped. Ruff, `compileall`, and `git diff --check` passed.
FINDINGS / CONCERNS: No OANDA requests or long runs started. Existing unrelated worktree changes were left untouched.
