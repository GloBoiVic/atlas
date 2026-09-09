# REVIEW — R001 Reuse the Existing Transaction Observation Kind

- **Status:** `FAIL`
- **Role:** `REVIEW`
- **Workstream:** `dogfood-02-protected-trade-lifecycle-closure`
- **Remediation ID:** `R001`
- **Branch:** `solo/dogfood-02-protected-trade-lifecycle-closure`
- **Base SHA:** `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Origin:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/VALIDATION.md`, Blocking Finding

## Review Authority

Independently review the original request, frozen PLAN.md and ARCHITECTURE.md, T001/T002 receipts, the immutable root validation failure, and the complete R001 remediation chain. Judge whether R001 resolves the demonstrated persistence-contract defect within approved scope, preserves all closure/lifecycle safety boundaries, introduces no migration or capital authority, and leaves zero unresolved IMPORTANT or CRITICAL findings.

## Worker Evidence

### Immutable Receipt

- **ROLE:** `REVIEW`
- **STATUS:** `FAIL`
- **ARTIFACT:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/remediations/R001-dogfood-02-protected-trade-lifecycle-closure/REVIEW.md`
- **FILES CHANGED:**
  - This review artifact only. No product, test, generated-client, model, migration, or prior-evidence file was modified by REVIEW.
- **CHECKS / EVIDENCE:**
  - Reviewed the original request in `PLAN.md`, frozen `PLAN.md`/`ARCHITECTURE.md`, immutable T001/T002 BUILD receipts, root validation failure, R001 BUILD/VALIDATION receipts, and the complete diff from base `c0079e7`.
  - Focused closure/runtime/API tests: `200 passed, 1 warning`.
  - Broad safe backend suite: `1265 passed, 4 skipped, 115 deselected, 4 warnings`.
  - Changed-surface Ruff format/check and production-source Pyright passed; `git diff --check` passed.
  - `npm run check:web` passed: formatting, typecheck, 18 frontend test files / 91 tests, and production build. Existing ESLint output was 242 warnings and 0 errors.
  - `uv run alembic current` reported `0023_paper_runtime_activation (head)` and `uv run alembic check` reported no new operations. The model and migration both accept `TRANSACTION_DETAIL`; no executable/test source retains `TRADE_CLOSE_TRANSACTION`.
  - Direct deterministic reproduction: after one lifecycle-advanced close, changing aggregate `realized_pl` from the first read to `999` on a later coordinator read produced `LIFECYCLE_ADVANCED`, findings only `TRADE_LIFECYCLE_ADVANCED`, and a second appended observation. The returned closure used `999` rather than surfacing a contradiction.
  - Direct deterministic OANDA check: an exact closing transaction with no provider `reason` returned `CONFLICT`/unattributable rather than unresolved optional enrichment.
  - Dedicated PostgreSQL integration was unavailable because `ATLAS_TEST_DATABASE_URL` was not configured; no real credentials, runtime, activation, Dogfood reconciliation, or broker mutation was used.
- **FINDINGS / CONCERNS:**
  - **IMPORTANT — PRODUCT / DEFECT:** Contradictory closure economics are not detected or surfaced. `PaperBrokerObservation` deduplicates only an identical normalized-facts fingerprint (`backend/persistence/paper_execution_repository.py:355-363`), while the coordinator accepts the latest `trade_closure` and links observations without comparing prior exact CLOSED evidence (`backend/paper/reconciliation.py:321-382`, `646-735`). A changed aggregate or matching close-transaction economic value therefore becomes a new append-only observation and is returned as successful `LIFECYCLE_ADVANCED`, with no `CONFLICT` finding. This violates frozen ARCHITECTURE.md 3.2.8 and acceptance criterion 31; append-only preservation alone is insufficient because the contradiction is silently selected for the result.
  - **MINOR — PRODUCT / DEFECT:** Missing close-transaction `reason` is classified as an attribution `CONFLICT` (`backend/integrations/oanda/reconciliation.py:1517-1521`, `765-768`), causing the coordinator to record `CONFLICT` plus `UNRESOLVED` (`backend/paper/reconciliation.py:359-375`). A valid exact transaction whose optional cause field is absent should retain the proven lifecycle and expose unresolved enrichment without manufacturing a conflict, per ARCHITECTURE.md 3.3 and 6.
  - **MINOR — PRODUCT / DEFECT:** The new close-read path accepts arbitrarily long numeric provider transaction IDs through `_positive_id`, while `PaperBrokerObservationModel.provider_transaction_id` is `String(64)` (`backend/integrations/oanda/reconciliation.py:221-238`, `backend/persistence/models.py:1055`). A malformed or future oversized provider ID can pass the in-memory contract and fail at the append boundary. Real OANDA IDs are expected to be short and the failure is fail-closed, but the provider/domain bound is not aligned with the existing persistence bound.
  - **TESTING GAP:** No dedicated PostgreSQL integration exercised the actual append/apply transaction after the read-kind correction; static model/migration inspection and Alembic checks passed. No operational Dogfood read was attempted because it is explicitly unauthorized before merge approval.
