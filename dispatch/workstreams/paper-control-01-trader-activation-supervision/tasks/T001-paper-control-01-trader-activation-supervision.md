# T001 — PAPER frontend control protocol

- **Workstream:** `paper-control-01-trader-activation-supervision`
- **Status:** DONE
- **Role:** BUILD
- **Depends on:** none

## Owned files

- `frontend/lib/api-client.ts`
- `frontend/lib/paper-control.ts`
- `frontend/tests/api_client.test.ts`
- focused pure-helper tests as appropriate

## Deliver

- Add typed methods for existing PAPER activation, activation detail, and stop contracts.
- Add exact percentage-string to decimal-ratio-string Risk conversion without binary floating-point arithmetic.
- Add lifecycle and operational-phase presentation helpers as needed by activation and supervision.
- Preserve the stable activation request-body contract and exact decimal-string `riskPerTrade` wire value.

## Constraints

- No page-level UI.
- Use existing generated OpenAPI request and response types.
- Do not modify generated API types unless intake proves them stale.
- Do not change backend, Risk, runtime, execution, broker, persistence, or migration semantics.

## Required checks

```bash
npx vitest run \
  --config frontend/vitest.config.ts \
  frontend/tests/api_client.test.ts \
  frontend/tests/paper_control.test.ts
```

Cover activation POST body, exact decimal-string Risk conversion including `1% -> "0.01"` and fractional percentages, invalid/zero/100% Risk, detail GET, stop POST body, and lifecycle labels.

## Worker Evidence

- **Status:** DONE
- **Files changed:** `frontend/lib/api-client.ts`, `frontend/lib/paper-control.ts`, `frontend/tests/api_client.test.ts`, `frontend/tests/paper_control.test.ts`, this task artifact.
- **Checks/evidence:** Required focused Vitest command passed: 2 files, 25 tests. `npm run typecheck:web`, Prettier check on changed TypeScript files, and `git diff --check` passed.
- **Concerns:** None. No generated API types, backend, page UI, runtime, PAPER activation, OANDA, or broker behavior was changed.
