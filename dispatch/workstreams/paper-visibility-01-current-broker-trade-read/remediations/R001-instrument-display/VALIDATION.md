# VALIDATION - R001 Instrument Display

- **Workstream:** `paper-visibility-01-current-broker-trade-read`
- **Branch:** `solo/paper-visibility-01-current-broker-trade-read`
- **Remediation:** `R001-instrument-display`
- **Role:** `VALIDATE` (lead fallback)
- **Date:** `2026-09-08`
- **Worker note:** A fresh validation worker was attempted but unavailable because the worker balance was exhausted. The lead independently ran the executable checks and recorded the evidence below.

## Verdict: PASS

All explicit instrument fields rendered by the frontend now pass through the shared
`formatInstrumentDisplay` helper. Provider/API values remain unchanged on the wire,
and the DELETE confirmation payload remains authoritative `EUR/USD` rather than the
display-only `EURUSD` value.

## Evidence

| Check | Result |
|---|---|
| Focused frontend tests | PASS - 8 files, 61 tests, including EUR_USD/EUR/USD/XAU_USD/BTC_USD cases and DELETE payload regression |
| `npm run check:web` | PASS - Prettier, ESLint 0 errors with 242 existing warnings, TypeScript, 87 tests, and production build |
| Broker API regression | PASS - `uv run pytest backend/tests/test_api_paper_broker_state.py`, 9 passed |
| `git diff --check` | PASS |
| E2E | Not run - existing API port/dedicated database harness limitation documented by the parent validation |

## Scope Verification

- `frontend/lib/instrument.ts` strips `_` and `/` without changing casing or
  alphanumeric content, so `EUR_USD`, `EUR/USD`, `XAU_USD`, and `BTC_USD` render as
  `EURUSD`, `EURUSD`, `XAUUSD`, and `BTCUSD`.
- Explicit instrument displays are formatted in broker state, PAPER capability,
  historical-data capability, Strategy history, experiment comparison, experiment
  results, experiment setup, and experiment status.
- Shared `marketIdentity` formats its display value, while `instrumentIdentity`
  remains raw because `confirmationFacts` uses it for the destructive DELETE
  confirmation contract.
- `frontend/components/experiments/experiment-status.tsx` formats only the rendered
  Market fact. The deletion request still sends the original provider/domain
  instrument string; `frontend/tests/experiment_delete.test.tsx` passes.
- No backend, API schema, OANDA reader, runtime, Risk, execution, persistence,
  migration, or broker behavior changed as part of R001.
- Existing OPEN broker badge colors remain intact.

## Findings

- No blocking findings.
- Existing full-suite lint warnings and E2E environment limitation are not R001
  regressions.
