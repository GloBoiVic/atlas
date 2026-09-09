# R001 - Instrument Display Format

- **Remediation ID:** `R001`
- **Status:** `DONE_WITH_CONCERNS`
- **Role:** BUILD
- **Workstream:** `paper-visibility-01-current-broker-trade-read`
- **Branch:** `solo/paper-visibility-01-current-broker-trade-read`
- **Origin finding:** Post-REVIEW trader feedback (2026-09-08) — instrument rendered as `EUR_USD` with underscore/slash; trader requires `EURUSD` and translation to other instruments (`XAUUSD`, `BTCUSD`). Source: `dispatch/workstreams/paper-visibility-01-current-broker-trade-read/REVIEW.md:60` (frontend copy) and user request.
- **Finding severity:** `MINOR` — approved-scope trader-facing copy defect (instrument presentation)
- **Related original task(s):** T001

## Approved requirement or invariant violated

PLAN Frontend presentation requires short intuitive trader-facing copy and correct instrument display (`PLAN.md:78` Instrument, `PLAN.md:212-213` "derive direction ... show instrument"). Current `frontend/components/paper-broker-state.tsx:79` renders `trade.instrument` verbatim (`EUR_USD`), which does not match trader convention `EURUSD`. Same applies to other instrument surfaces that expose OANDA `EUR_USD` or domain `EUR/USD` with separators.

## Exact remediation outcome

- Display instruments without separators: `EUR_USD` → `EURUSD`, `EUR/USD` → `EURUSD`, `XAU_USD` → `XAUUSD`, `BTC_USD` → `BTCUSD`, etc. Strip `_` and `/` globally, preserve casing and alphanumerics, no new tokens or colors.
- Add `frontend/lib/instrument.ts` with `formatInstrumentDisplay(instrument: string): string` (exported, unit-tested) implementing `instrument.replaceAll('_','').replaceAll('/','')` with guard for empty/undefined.
- Apply formatter wherever UI displays an instrument: at minimum `frontend/components/paper-broker-state.tsx:79` (BrokerTradeCard), and other active instrument surfaces (`frontend/components/paper-status.tsx:62`, `frontend/components/data-overview.tsx:90`, and any other `*.instrument` display paths identified as trader-visible). Backend payloads and API contracts remain unchanged (still `EUR_USD` wire format).
- Update focused frontend tests to assert `EURUSD` instead of `EUR_USD`/`EUR/USD` where instrument is trader-visible (e.g., `frontend/tests/paper_broker_state.test.tsx`, `frontend/tests/overview.test.tsx`, `frontend/tests/paper_status.test.tsx`). Tests remain deterministic, no Dogfood hardcoding.
- Preserve existing badge color work (`frontend/components/paper-broker-state.tsx:66` OPEN=positive/WARN) already on branch; ensure instrument change does not revert it.
- Keep API, backend, runtime, Risk, persistence, migration, and broker semantics unchanged.

## Affected implementation seams

- `frontend/lib/instrument.ts` (new)
- `frontend/components/paper-broker-state.tsx`
- `frontend/components/paper-status.tsx`
- `frontend/components/data-overview.tsx` (if instrument trader-visible)
- Any other identified `instrument` display components (strategy-history, experiment-* surfaces) — only if trader-visible instrument string, backend unchanged
- `frontend/tests/paper_broker_state.test.tsx`
- `frontend/tests/overview.test.tsx`
- `frontend/tests/paper_status.test.tsx`
- Other frontend tests covering instrument display as needed
- `frontend/lib/instrument.test.ts` or equivalent unit coverage

## Explicitly out of scope

- Backend instrument enums, API schemas, OANDA normalization, or wire format changes (still `EUR_USD`).
- New color tokens, palette, or visual redesign beyond instrument string formatting (badge color already applied separately and preserved).
- Strategy/Risk/execution, runtime activation, reconciliation, persistence, migrations, LIVE, or deployment changes.
- Provider-neutral Position netting or instrument capability expansion.

## Regression evidence required

- New instrument formatter unit tests (including `EUR_USD`→`EURUSD`, `EUR/USD`→`EURUSD`, `XAU_USD`→`XAUUSD`, `BTC_USD`→`BTCUSD`, empty/invalid guard).
- Focused component tests for broker state / overview / paper status pass with new expected strings.
- `npm run check:web` (format:check, lint, typecheck, test:web, build:web) passes.
- `uv run ruff format --check` / `pyright` (if backend touched) — no backend change expected, so unchanged.
- `git diff --check` clean.
- No backend test regression (`uv run pytest -m "not integration and not external"` not required but spot-check broker-state backend tests unchanged).

## Worker Evidence

```text
ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: dispatch/workstreams/paper-visibility-01-current-broker-trade-read/remediations/R001-instrument-display/BUILD.md
FILES CHANGED:
- frontend/lib/instrument.ts
- frontend/lib/instrument.test.ts
- frontend/components/paper-broker-state.tsx
- frontend/components/paper-status.tsx
- frontend/components/data-overview.tsx
- frontend/components/strategy-history.tsx
- frontend/components/experiment-comparison.tsx
- frontend/components/experiments/shared.ts
- frontend/components/experiments/experiment-results.tsx
- frontend/components/experiments/experiment-setup.tsx
- frontend/components/experiments/experiment-status.tsx
- frontend/tests/paper_broker_state.test.tsx
- frontend/tests/paper_status.test.tsx
- frontend/tests/overview.test.tsx
- frontend/tests/data_overview.test.tsx
- frontend/tests/strategy_setup.test.tsx
- frontend/tests/experiment_results.test.tsx
- dispatch/workstreams/paper-visibility-01-current-broker-trade-read/remediations/R001-instrument-display/BUILD.md
CHECKS / EVIDENCE:
- Focused Vitest: 8 files, 61 tests passed, including EUR_USD/EUR/USD/XAU_USD/BTC_USD formatter cases and DELETE payload regression.
- `npm run check:web`: Prettier passed, ESLint 0 errors with 242 pre-existing warnings, TypeScript passed, 87 frontend tests passed, production build passed.
- `uv run pytest backend/tests/test_api_paper_broker_state.py`: 9 passed.
- `git diff --check`: passed.
FINDINGS / CONCERNS:
- An initial partial implementation caused the formatted display value to leak into the DELETE confirmation payload; this was corrected by keeping authoritative API facts raw and formatting only rendered UI values. The deletion regression test passes.
- E2E was not run; existing harness has a known API-port/dedicated-database limitation documented in the parent validation.
```
