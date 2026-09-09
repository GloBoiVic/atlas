# VALIDATION - R001 Reuse the Existing Transaction Observation Kind

- **Status:** `PASS`
- **Role:** `VALIDATE`
- **Workstream:** `dogfood-02-protected-trade-lifecycle-closure`
- **Remediation ID:** `R001`
- **Branch:** `solo/dogfood-02-protected-trade-lifecycle-closure`
- **Base SHA:** `c0079e7b3f4f8bfbd00754060d37f7fdb925d649`
- **Validated:** 2026-09-09
- **Origin:** `dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/VALIDATION.md`, Blocking Finding

## Immutable Receipt

### ROLE

`VALIDATE`

### STATUS

`PASS`

### ARTIFACT

`dispatch/workstreams/dogfood-02-protected-trade-lifecycle-closure/remediations/R001-dogfood-02-protected-trade-lifecycle-closure/VALIDATION.md`

### FILES CHANGED

- R001 implementation scope: `backend/paper/persistence_contracts.py`
- R001 implementation scope: `backend/integrations/oanda/reconciliation.py`
- R001 test scope: `backend/tests/paper/test_reconciliation.py`
- R001 test scope: `backend/tests/integrations/test_oanda_reconciliation.py`
- This validation receipt only: this artifact

### CHECKS / EVIDENCE

- Exact close-transaction observations use existing `PaperObservationReadKind.TRANSACTION_DETAIL` in every executable close-read path. No executable or test source contains `TRADE_CLOSE_TRANSACTION`; remaining matches are historical evidence text only.
- `read_trade_close_transaction()` remains a distinct protocol/provider method. OANDA uses the bounded account-scoped transaction GET, exact requested transaction/Trade IDs, and provider normalization before returning to the coordinator. Deterministic tests assert GET-only requests and exact attribution.
- V2 closure facts and semantics remain intact: focused OANDA tests assert `ATLAS_PAPER_BROKER_FACTS_V2`, aggregate close facts, multiple-ID `MULTIPLE` behavior without fan-out, provider-cause mappings, exact attribution conflicts, and `TradeReduce.price` (`1.11035`) rather than deprecated top-level OrderFill `price` (`9.99999`).
- Focused T001 tests: `uv run pytest backend/tests/paper/test_persistence_contracts.py backend/tests/integrations/test_oanda_reconciliation.py` -> `42 passed`.
- Focused T002/API tests: `uv run pytest backend/tests/paper/test_reconciliation.py backend/tests/runtime/test_runtime_activation.py backend/tests/test_api_paper.py` -> `145 passed, 1 warning`. CLOSED composition remains `LIFECYCLE_ADVANCED`, `FILLED_PROTECTED` is not rewritten, optional cause failure remains unresolved without downgrading lifecycle, and linked observations remain covered.
- Required runtime cross-seam test: `uv run pytest backend/tests/runtime/test_runtime_completion_cross_seam.py` -> `13 passed`.
- Broad safe backend suite: `uv run pytest -q -m "not integration and not external"` -> `1265 passed, 4 skipped, 115 deselected, 4 warnings`.
- Changed-surface checks over the four R001 implementation/test files: `uv run ruff format --check` -> `4 files already formatted`; `uv run ruff check` -> `All checks passed`; production-source `uv run pyright backend/paper/persistence_contracts.py backend/integrations/oanda/reconciliation.py` -> `0 errors, 0 warnings, 0 informations`.
- `git diff --check` passed. `backend/persistence/models.py` and `backend/persistence/migrations/**` have no diff. No migration was generated.
- Current model CHECK contains every `PaperObservationReadKind` value, including `TRANSACTION_DETAIL`; the migration `0022` CHECK contains the same accepted value. Direct enum-to-model assertion passed. `uv run alembic current` -> `0023_paper_runtime_activation (head)`; `uv run alembic check` -> `No new upgrade operations detected.`
- Generated client freshness: current `create_app().openapi()` -> `openapi-typescript 7.13.0` -> repository Prettier -> byte-identical `frontend/lib/api.generated.ts`.
- `npm run check:web` passed: formatting, typecheck, 18 frontend test files / 91 tests, and production build. ESLint reported 242 existing warnings and 0 errors; no R001 frontend change was made.
- All provider evidence was deterministic fake/MockTransport or test doubles. No runtime start, activation, credentials, real reconciliation, Risk evaluation, or broker mutation occurred.

### FINDINGS / CONCERNS

- **PRODUCT / DEFECT:** None. The blocking unsupported-read-kind persistence defect is resolved without changing the model or migration contract.
- **REGRESSION / DEFECT:** None found. V2 facts, exact attribution, `TradeReduce.price`, exit-cause mapping, lifecycle status, and execution-outcome semantics remain covered and passing.
- **TOOLING / NEW SCOPE:** None attributable to R001. The frontend gate emits only the pre-existing 242 ESLint warnings noted above; they are outside this remediation and do not fail the gate.
