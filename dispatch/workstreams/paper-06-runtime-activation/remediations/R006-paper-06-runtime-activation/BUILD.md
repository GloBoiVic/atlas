# R006 — Exact `risk_per_trade` persistence

- **Remediation ID:** `R006-paper-06-runtime-activation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin finding and source artifact:** Original `REVIEW.md` `IMPORTANT-03`
- **Finding severity:** `IMPORTANT` / `PRODUCT BLOCKER`
- **Related original task(s):** T001, T002, T008
- **Approved requirement or invariant violated:** PLAN scope/acceptance items 1, 8, 17–18 and ARCHITECTURE §§3.1, 4.1, 12.1 — the approved canonical `RiskConfig.risk_per_trade` must survive request, domain validation, PostgreSQL persistence, load, and same-ID activation replay exactly without binary floating point or database rounding.
- **Exact remediation outcome:** Replace the unmerged `NUMERIC(30,10)` runtime activation representation with the narrowest exact PostgreSQL representation that preserves accepted canonical Decimal values, update dependent persistence contracts as needed, and prove ordinary, >10-fractional-digit, near-boundary, exact round-trip, same-ID replay, and changed-risk identity-conflict behavior. Keep migration history clean under the pre-merge 0023 policy; do not add speculative follow-up migrations.
- **Affected implementation seams:** `backend/persistence/models.py`, `backend/persistence/migrations/versions/0023_paper_runtime_activation.py`, `backend/persistence/runtime_repository.py`, activation/domain/API contracts only as directly required, and deterministic plus dedicated PostgreSQL tests.
- **Explicit out-of-scope items:** No arbitrary new precision restriction solely for the schema workaround, no binary float, no Risk-policy change, no activation identity redesign, no broker/runtime lifecycle change, no credentials, no activation, no LIVE/PAPER operation, and no real OANDA request or mutation.
- **Regression evidence required:** Real PostgreSQL round trip for `0.01`, `0.12345678901`, and a small positive value near the prior scale boundary; exact loaded `RiskConfig`; same-ID exact replay succeeds; same-ID changed risk value conflicts; migration upgrade/downgrade/upgrade, `alembic current`, `alembic check`; changed-slice Ruff/Pyright and `git diff --check`.

## Worker Evidence

Implemented the approved exact `risk_per_trade` persistence remediation.

### Files changed

- `backend/persistence/models.py` — runtime activation `risk_per_trade` now uses
  unconstrained SQLAlchemy `Numeric()` with Decimal result handling.
- `backend/persistence/migrations/versions/0023_paper_runtime_activation.py` —
  the unmerged migration now defines PostgreSQL `NUMERIC` without precision or
  scale; no repair migration was added.
- `backend/tests/runtime/test_runtime_risk_precision.py` — request/domain
  validation, unconstrained Decimal model metadata, ordinary, >10-fractional-
  digit, and near-boundary coverage.
- `backend/tests/integration/test_runtime_repository.py` — dedicated
  PostgreSQL load → `RiskConfig`, exact replay, and changed-risk identity
  conflict coverage.
- `backend/tests/integration/test_runtime_migration.py` — dedicated schema
  assertion for unconstrained PostgreSQL `NUMERIC`.

### Checks and evidence

- Focused deterministic activation/migration tests: **42 passed**.
- Runtime/persistence focused tests: **124 passed**.
- Safe backend suite (`not integration and not external`): **1107 passed, 4
  skipped, 115 deselected**, with four existing warnings.
- Changed-slice Ruff check/format and Pyright: **passed**; Pyright reported
  zero diagnostics.
- `git diff --check`: **passed**.
- Dedicated PostgreSQL runtime repository/migration tests: **6 skipped**;
  `ATLAS_TEST_DATABASE_URL` was not configured, so no dedicated database was
  available for this worker run. The tests cover migration
  upgrade/downgrade/upgrade, `current`/`check`, exact PostgreSQL round trips,
  replay, and conflict behavior when available.
- Read-only local `alembic current` reported `0020_fix_snapshot_guard`, and
  `alembic check` reported the target database was not up to date. The local
  non-dedicated database was not migrated or otherwise changed.
- No credentials, OANDA requests, broker mutation, activation, PAPER/LIVE
  operation, Risk-policy change, R004/R005 behavior change, or Git-history
  operation was performed.

### Concerns / handoff

- Dedicated PostgreSQL execution remains an environment-dependent validation
  concern; run the two integration files against a dedicated `*_test` database
  before final workstream validation.
