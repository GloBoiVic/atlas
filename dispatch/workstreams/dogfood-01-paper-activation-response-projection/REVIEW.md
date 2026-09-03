# REVIEW — Dogfood 01 PAPER Activation Response Projection Remediation

## Dispatch

- **Role:** `REVIEW`
- **Workstream:** `dogfood-01-paper-activation-response-projection`
- **Branch:** `solo/dogfood-01-paper-activation-response-projection`
- **CWD:** `/Users/vike/Desktop/atlas`
- **Task:** `NONE`
- **Owned artifact:** `dispatch/workstreams/dogfood-01-paper-activation-response-projection/REVIEW.md`

## Independent verdict

**PASS.** The implementation is the frozen one-line production projection repair
with necessary real-projection regression coverage. No unresolved CRITICAL or
IMPORTANT finding remains.

## Findings

| Severity | Classification | Type | Finding |
| --- | --- | --- | --- |
| CRITICAL | PRODUCT | DEFECT | None observed. |
| IMPORTANT | REGRESSION | DEFECT | None observed. |
| MINOR | TOOLING | DEFECT | `VALIDATION.md` says the T001 header is still `READY`, but the current T001 receipt and PLAN say `DONE`; evidence metadata only. |
| MINOR | TOOLING | NEW SCOPE | The existing TestClient Starlette/httpx deprecation warning remains; it is pre-existing and non-blocking. |

The production diff is exactly one added `requested_at` field in
`PaperRuntimeActivation.to_json()`, sourced from the already UTC-normalized
`self.requested_at` and using the established `Z` convention. The test diff
correctly replaces the old hand-written activation payload with real
`PaperRuntimeActivation`, `PaperRuntimeActivationResult`, and
`PaperRuntimeStatus` projections. The unrelated parameter-name cleanup in a
not-found fake is non-functional and does not affect the verdict.

## Contract and path review

- Direct domain projection validates through `PaperRuntimeActivationResponse`
  and emits exact `requestedAt` plus string `riskPerTrade` (`"0.01"`).
- FastAPI create, active, detail/status, and stop paths each exercise the real
  projection and assert HTTP 200, exact `requestedAt`, and string
  `riskPerTrade`.
- `requested_at` remains outside `immutable_json()`. The production diff does
  not alter activation identity, idempotency, lifecycle transitions,
  transaction behavior, Risk, execution, or broker seams.
- Existing numeric-wire rejection, Decimal precision, replay/identity, and
  lifecycle tests remained green. No response model, alias, schema, or
  persistence change was introduced.

## Checks and evidence

- Independent focused run: **60 passed, 1 pre-existing warning** across the API,
  activation, persistence, and risk-precision suites.
- `git diff --check`: passed.
- Changed-file format, lint, and pyright results reported by VALIDATE: passed.
- Working tree review shows only the one production file, focused API test
  changes, expected `dispatch/ACTIVE.md` operational state, and workstream
  evidence artifacts.

## Capital-safety evidence and limitations

- Tests used deterministic fixed values, fakes, and in-memory FastAPI
  `TestClient`; no production service or database activation was used.
- No `atlas-runtime` process was running during review. No runtime start,
  OANDA contact, new or existing activation mutation, broker action, or other
  capital-capable operation occurred.
- No integration database, live provider, or durable-row replay check was run;
  those are outside the frozen projection-only validation boundary.

## Merge recommendation

**Recommend merge approval.** The minor evidence warning and pre-existing
deprecation warning do not block this narrow, capital-safe repair. This review
does not merge or alter Git history.
