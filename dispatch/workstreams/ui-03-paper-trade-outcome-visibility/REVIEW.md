# REVIEW - UI 03 PAPER Trade Outcome Visibility

## Verdict

- **Status:** `PASS`
- **Workstream:** `ui-03-paper-trade-outcome-visibility`
- **Role:** `REVIEW`
- **Branch:** `solo/ui-03-paper-trade-outcome-visibility`
- **Base:** `main` at `664b19c902656b37271158c55faf7f7d19cfa840`
- **Finding disposition:** F-001 and F-002 are resolved by the approved R001 and R002 remediation chains.
- **Blocking findings:** None. No unresolved `CRITICAL` or `IMPORTANT` finding remains.

## Inputs Reviewed

- Approved `PLAN.md`, including all acceptance criteria, scope boundaries, safety constraints, and validation plan.
- Immutable original T001 and T002 BUILD receipts and task contracts.
- Root `VALIDATION.md`, including original findings F-001 and F-002, its scope review, checks, and browser/safety limitations.
- R001 and R002 `BUILD.md`, `VALIDATION.md`, and `REVIEW.md` chains.
- Current `HEAD` and `main`; both resolve to the recorded base commit.
- Complete base-to-worktree diff, including modified files, untracked application/test files, generated output, dispatch receipts, and the workstream state marker.
- Current backend domain, PAPER persistence models/contracts, Fill and reconciliation seams, API schemas/routes/application wiring, generated OpenAPI client, frontend client/components, and adjacent tests.
- `DOMAIN.md`, `README.md`, and the fresh Web Interface Guidelines.
- Explicit user safety constraints for this final review.

## Acceptance Coverage

- **Criteria 1-7:** `GET /api/v1/paper/trades` exists, is GET-only, database-only, mutation-free, bounded to `1..50`, defaults to `10`, and returns newest-close-first results. The route delegates to the read service; focused API tests cover bounds, default/explicit limits, POST rejection, and read-only wiring.
- **Criteria 8-15:** Eligibility requires a durable Fill, `LIFECYCLE_ADVANCED`, schema-V2 `TRADE_DETAIL`, matching `CLOSED` Trade evidence, and valid required closure facts. Entry fields use durable Fill values; Stop and Target use confirmed durable protection only. R001 applies the bound after composition and chronology, so ineligible rows cannot consume the result limit.
- **Criteria 16-21:** Close time, average close price, realized P/L, financing, and dividend adjustment come from parsed CLOSED Trade evidence. No Net P/L is calculated; the API and UI keep the three economics fields separate. R002 presents durable actual initial risk with the established monetary formatter, while market prices retain price formatting.
- **Criteria 22-26:** Exact exit cause is returned only for exactly one recorded closing transaction ID with matching schema-V2 transaction evidence attributable to the same attempt and Trade. Multiple, unresolved, missing, mismatched, malformed, and unknown cause evidence remains unavailable. No price, P/L sign, broker flatness, or Strategy intent inference is used; Dogfood 02 is not special-cased.
- **Criteria 27-30:** Strategy catalog name is composed through the durable Strategy relationship, with persisted attempt Strategy key/version identity. No migration or execution/reconciliation semantic change is present. `frontend/lib/api.generated.ts` is byte-current with freshly generated OpenAPI output.
- **Criteria 31-36:** Overview has compact `Recent PAPER trades`; PAPER has fuller `Completed PAPER trades`. Direction, Strategy/version, entry/exit, protection, economics, close time, exact trader-facing causes, and non-zero dividend adjustment are covered. Loading, empty, error, retry, and selected timezone states are covered. The new history UI does not expose UUIDs, provider IDs/reasons, or internal state vocabulary as primary content.
- **Criteria 37-39:** Existing current broker, capability, runtime, Overview, Strategy, Experiment, and PAPER behavior remains wired and independently readable. The history failure state is non-destructive and does not imply current broker flatness. No activation, reconciliation, or broker controls were added.

## Finding Disposition

### F-001 - Bounded history eligibility

- **Classification:** `PRODUCT / DEFECT`
- **Disposition:** Resolved by approved R001.
- **Evidence:** `PaperTradeHistoryReadService.list()` loads candidate evidence without pre-composition SQL limiting, validates durable eligibility, parses close times to UTC, sorts descending by close time with deterministic attempt-ID tie-breaking, and only then applies `composed[:limit]`. R001 regression coverage retains an eligible CLOSED Trade behind an ineligible candidate and verifies offset-normalized chronology.

### F-002 - Initial-risk presentation

- **Classification:** `PRODUCT / DEFECT`
- **Disposition:** Resolved by approved R002.
- **Evidence:** Fuller history renders `initialRisk` with `formatMoney`, producing account-money formatting with currency and two decimals. Entry, Exit, Stop, and Target remain on `formatPrice`. The R002 regression proves a non-price risk value is not rendered at price precision.

### New findings

None. No `PRODUCT`, `REGRESSION`, or `TOOLING` finding classified as `DEFECT` or `NEW SCOPE` was identified in the final review.

## Verification Evidence

- Focused backend: `uv run pytest backend/tests/paper/test_trade_history.py backend/tests/test_api_paper.py` -> **30 passed**, one existing Starlette/httpx deprecation warning.
- Focused frontend: `npx vitest run --config frontend/vitest.config.ts frontend/tests/api_client.test.ts frontend/tests/overview.test.tsx frontend/tests/paper_status.test.tsx` -> **29 passed**.
- Broad safe backend: `uv run pytest -m "not integration and not external"` -> **1296 passed, 4 skipped, 115 deselected, 4 warnings**.
- Full web gate: `npm run check:web` passed Prettier, TypeScript, **94 frontend tests**, production build, and ESLint with existing warnings only (**242 warnings, 0 errors**).
- Scoped backend formatting/lint: six affected backend files already formatted and Ruff checks passed.
- Scoped history Pyright: **0 errors, 0 warnings, 0 informations**.
- Migration check: `uv run alembic check` -> **No new upgrade operations detected**.
- Generated contract: fresh `create_app().openapi()` generation through `openapi-typescript 7.13.0` and repository Prettier compared byte-identically with `frontend/lib/api.generated.ts`.
- Whitespace: tracked and untracked application files passed `git diff --check`/no-index whitespace checks.
- The existing repository-wide backend formatting, Ruff, Pyright, and frontend ESLint baseline findings remain outside this slice and are non-blocking residual tooling limitations.

## Scope And Safety Judgment

- The complete diff contains only the approved backend history/API wiring and tests, frontend client/presentation and tests, generated client output, and workstream/dispatch receipts. No migration, persistence-model, runtime, Risk, Strategy, OANDA integration, execution, or reconciliation file was changed.
- The history endpoint uses only SQLAlchemy reads against durable attempt, Strategy, and schema-V2 observation records. It does not call OANDA, inspect mutable broker inventory, trigger reconciliation, start runtime, or expose broker mutation authority.
- No `atlas-runtime` process was started, PAPER was not activated, no credentialed external check was run, no seeded/integration test activity was run, and no broker mutation or capital-capable request occurred during this final review. Unit tests that exercise provider normalization use local recorded/mocked inputs only.
- The immutable root validation records that an existing browser server performed one current broker-state request before fetch interception. That historical validation harness fact is disclosed here; it was not the UI 03 history endpoint and no such request was made during this final review.
- PostgreSQL integration validation remains unavailable because the dedicated `ATLAS_TEST_DATABASE_URL` environment was unavailable. This is a non-blocking tooling limitation; the focused service/API tests, source review, migration check, and broad safe regression passed.
- No new branch-specific browser server was started. UI behavior is covered by focused/full frontend tests, source review, and the prior recorded fixture evidence for desktop/mobile, timezone, and state handling.

## Merge Recommendation

**PASS.** The approved UI 03 feature and both approved remediations satisfy the acceptance criteria with no unresolved blocking finding. Merge only after explicit developer merge approval. This review does not merge, commit, switch branches, or perform GIT END.

## Completion Receipt

```text
ROLE: REVIEW
STATUS: PASS
ARTIFACT: dispatch/workstreams/ui-03-paper-trade-outcome-visibility/REVIEW.md
FILES CHANGED BY REVIEW: dispatch/workstreams/ui-03-paper-trade-outcome-visibility/REVIEW.md only
CHECKS / EVIDENCE: Independent final source, contract, complete-diff, persistence, API, frontend, and Web Interface Guidelines review; focused backend 30 passed; focused frontend 29 passed; broad safe backend 1296 passed, 4 skipped, 115 deselected; npm run check:web passed with 94 frontend tests, TypeScript, Prettier, production build, and ESLint with 242 existing warnings and 0 errors; scoped Ruff/Pyright passed; Alembic check reported no new operations; generated OpenAPI comparison passed; git diff --check passed.
FINDINGS / CONCERNS: PASS - F-001 resolved by R001; F-002 resolved by R002; no unresolved CRITICAL or IMPORTANT PRODUCT/REGRESSION finding; no new DEFECT or NEW SCOPE finding. PostgreSQL integration and branch-specific browser validation were unavailable/not run and are recorded as non-blocking limitations. No OANDA network read, runtime startup, PAPER activation, broker mutation, or capital-capable action occurred during final review.
```
