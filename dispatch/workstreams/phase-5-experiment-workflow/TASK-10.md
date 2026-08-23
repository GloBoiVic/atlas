# TASK-10 — End-to-end regression and documentation alignment

- **Task:** Implement approved Phase 5 blueprint task 10 only.
- **Agent:** backend builder
- **Model:** gpt-5.6-luna (`openai/gpt-5.6-luna`)
- **Branch:** `feature/phase-5-experiment-workflow`

## Changed files

- `backend/tests/e2e_seed.py` — deterministic PostgreSQL fixture seeding and
  failed-Experiment fixture preparation; no OANDA access.
- `tests/e2e/global-setup.ts` — invokes the fixture seed against the explicitly
  supplied E2E database.
- `tests/e2e/experiment-workflow.spec.ts` — configure/coverage/create/run/result/
  Trade, invalid coverage, failed, zero-Trade, and terminal duplicate-run paths.
- `playwright.config.ts` — starts FastAPI and Next.js as separate local
  processes, passes the server-only API/database configuration, and fixes the
  browser timezone to UTC.

No product architecture/context or other dispatch artifact was changed.

## Outcome

Added a real cross-process Playwright harness. Global setup migrates and
truncates the supplied PostgreSQL test database, then seeds the deterministic
EMA Sweep Engulfing/OANDA-shaped EUR/USD StrategyVersion and DatasetSnapshot
fixture from the existing golden data. The harness starts FastAPI and Next.js;
it does not use Docker, OANDA credentials, workers, or external services.

The E2E scenarios cover the approved workflow and failure states. The browser
receipt is blocked in this environment because the Playwright Chromium binary
is not installed; therefore no browser scenario is claimed as covered.

## Exact receipts

Environment:

- macOS darwin, zsh
- Python 3.13.3, `.venv/bin/python`
- PostgreSQL 18.4, `postgresql+psycopg://vike@localhost:5432/atlas_test`
  supplied as `ATLAS_E2E_DATABASE_URL` (test database only)
- Playwright 1.55 configuration starts FastAPI on `127.0.0.1:8000` and Next.js
  on `127.0.0.1:3000`

Receipts:

- `.venv/bin/ruff check backend/tests/e2e_seed.py` → **passed**.
- `.venv/bin/python -m py_compile backend/tests/e2e_seed.py` → **passed**.
- `npm run lint:web` → **passed** (one non-blocking warning was removed in the
  harness setup).
- `npm run typecheck:web` → **passed**.
- `npm run test:web` → **9 passed** across 5 files.
- `ATLAS_E2E_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_test
  npm run test:e2e` → fixture migration/seed completed and both web servers
  started; Playwright then reported 5 failures before test execution because
  `~/Library/Caches/ms-playwright/chromium_headless_shell-1193/.../headless_shell`
  does not exist. Exact remedy reported by Playwright: `npx playwright install`.
- Phase 1–4 deterministic/golden regression:
  `ATLAS_TEST_DATABASE_URL=.../atlas_test ATLAS_DATABASE_URL=.../atlas_test
  .venv/bin/pytest -q backend/tests/integration/test_golden_flows.py` → **8
  passed in 203.88s**.
- Phase 1–4 deterministic unit regression:
  `.venv/bin/pytest -q backend/tests/strategies backend/tests/execution
  backend/tests/risk backend/tests/domain backend/tests/experiments` → **123
  passed in 2.74s**.
- A combined broader regression invocation exceeded the 120-second command
  limit before producing a completion receipt; its focused deterministic and
  golden replacements above completed successfully.

## Blockers

Full browser E2E is **blocked**, not passed: the required local Playwright
Chromium executable is absent. No Docker or OANDA workaround was introduced,
and no coverage is claimed for the five Playwright scenarios until the browser
dependency is installed. The fixture seed and server startup were verified
before that browser-launch blocker.

No Git mutations were performed.

## Follow-up receipt — Chromium installation and E2E rerun

Authorized dependency operation:

- `npx playwright install chromium` → **passed**. Downloaded Chromium
  `140.0.7339.186` (Playwright build `v1193`), FFMPEG build `v1011`, and the
  Chromium headless shell build `v1193`.

Documented E2E rerun:

- `ATLAS_E2E_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test'
  npm run test:e2e` → **failed: 0 passed, 5 failed** (2 workers; command
  completed in approximately 44 seconds).
- FastAPI started on `127.0.0.1:8000`; Next.js started on
  `127.0.0.1:3000`; Alembic fixture setup completed against the test database.
- Four workflow tests failed because Next.js development resources were blocked
  as cross-origin requests from `127.0.0.1` (`allowedDevOrigins` does not include
  that origin). Consequently configuration options did not load, coverage/run
  controls remained disabled, and the failed-Experiment action was unavailable.
- The existing `foundation.spec.ts` also failed independently: expected title
  `Atlas`, received `Atlas · Experiments`.

**Outcome:** Browser installation is no longer a blocker, but Phase 5 E2E is
still **blocked and not covered**. No success is inferred. No Git mutations or
other dependency operations were performed.

## Follow-up repair receipt — local dev origin and foundation title

Repairs applied only to the documented failures:

- `frontend/next.config.ts` now sets `allowedDevOrigins` to `['127.0.0.1']`
  only when `NODE_ENV === 'development'`; production builds receive no allowed
  development origins.
- `tests/e2e/foundation.spec.ts` now expects the approved title
  `Atlas · Experiments`.

Rerun receipt:

- `ATLAS_E2E_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_test'
  npm run test:e2e` → **failed: 0 passed, 5 failed** (5 tests, 2 workers).
- FastAPI, Next.js, Alembic fixture setup, and browser startup completed.
- The previous stale title assertion was repaired: the foundation test now
  reaches the heading assertion, but fails because no `Atlas` heading exists.
  The received page title is now correct: `Atlas · Experiments`.
- Workflow tests still fail precisely as follows: the valid and zero-Trade
  scenarios time out clicking disabled `Validate coverage`; invalid coverage
  likewise times out on the disabled validation control; failed Experiment
  reaches the page but cannot find the expected text `No trustworthy full result
  exists` after the run.

**Outcome:** The documented repairs are applied, but the full E2E suite remains
blocked with five failures. No additional fixes or success inference was made.
No Git mutations, dependency operations, or other dispatch-artifact changes
were performed.
