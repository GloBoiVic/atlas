# R006 — Exact `risk_per_trade` persistence

- **Status:** `PASS`
- **Role:** `VALIDATE`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **HEAD:** `0960191344595cf059cd99cb5bfb5ac6ce930dcd` (combined dirty BUILD state)
- **Origin:** Original `REVIEW.md` `IMPORTANT-03`
- **Validation mode:** Fresh independent, serial validation of the combined current HEAD after the approved R004–R006 BUILD batch.

## Decision

`PASS`. The accepted `Decimal` `risk_per_trade` survives request/domain
validation, PostgreSQL persistence, loading into `RiskConfig`, exact same-ID
replay, and changed-risk conflict detection. The corrected unconstrained
PostgreSQL `NUMERIC` representation passes the dedicated migration cycle and
schema assertion. Focused R004 and R005 functional regressions also passed.

## Scope and safety

- Verified repository root `/Users/vike/Desktop/atlas`, branch
  `solo/paper-06-runtime-activation`, and HEAD before validation. No branch or
  Git-history operation was performed.
- Read the original `REVIEW.md`, PLAN, ARCHITECTURE, original validation,
  R004–R006 BUILD/VALIDATION packets, the migration-child/pre-merge policy,
  `DOMAIN.md`, and directly affected model, migration, runtime repository,
  activation, Risk, and test seams.
- All PostgreSQL evidence below used the dedicated database explicitly:
  `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test'`.
  Integration tests and migration operations were run serially.
- No credentials, activation, real OANDA request, broker mutation, PAPER, LIVE
  operation, Risk-policy change, or capital-capable action was used. Provider
  regressions used local fakes/recorded transports only.

## R006 acceptance evidence

### Deterministic request/domain/model contract

Command:

```text
uv run pytest -q backend/tests/runtime/test_runtime_risk_precision.py backend/tests/test_migration_revision.py
```

Result: **6 passed**.

The deterministic coverage accepted and preserved these exact values without
float conversion:

| Value | Result |
| --- | --- |
| `0.01` | PASS |
| `0.12345678901` | PASS |
| `0.00000000001` | PASS |

The SQLAlchemy model metadata is `Numeric()` with `precision=None`,
`scale=None`, and `asdecimal=True`.

### Dedicated PostgreSQL persistence, Risk load, replay, and conflict

Command:

```text
ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' uv run pytest -q backend/tests/integration/test_runtime_repository.py -k 'activation_risk_round_trip_and_exact_identity_replay or activation_replay_conflict_and_single_slot'
```

Result: **4 passed, 1 deselected**. The three parametrized round trips proved:

- the database-loaded value remains an exact `Decimal` for all three values;
- `_activation_from_row` restores the exact value;
- `RiskConfig(loaded.risk_per_trade)` contains the exact value;
- same-ID exact replay returns the existing activation;
- same-ID changed-risk replay raises `PaperRuntimeIdentityConflict`.

The complete R006 repository/migration pair was then run serially:

```text
ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' uv run pytest -q backend/tests/integration/test_runtime_migration.py backend/tests/integration/test_runtime_repository.py
```

Result: **6 passed**.

### Old precision-loss reproduction

A read-only PostgreSQL query reproduced the original constrained-scale
behavior and contrasted it with the corrected type:

```text
NUMERIC(30,10): 0.1234567890, 0E-10
NUMERIC:        0.12345678901, 1E-11
```

The model and migration metadata independently report unconstrained
`Numeric()` (`precision=None`, `scale=None`, `asdecimal=True` for the model).

### Migration policy and lifecycle

The dedicated migration test passed the required schema assertion and
upgrade → downgrade to `0022_paper_persistence` → upgrade cycle. The same
cycle was also run directly against the dedicated database and succeeded.

Final dedicated checks:

```text
ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' ATLAS_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' uv run alembic current
→ 0023_paper_runtime_activation (head)

ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' ATLAS_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' uv run alembic check
→ No new upgrade operations detected.
```

`alembic history` confirms the linear child relationship
`0022_paper_persistence → 0023_paper_runtime_activation`. The only runtime
migration file is `0023_paper_runtime_activation.py`; its `NUMERIC` constant
is `sa.Numeric()` without precision or scale. No speculative repair migration
was added.

## R004/R005 regression evidence

The focused R004 safety/repeated-runtime selection passed:

```text
uv run pytest -q backend/tests/runtime/test_runtime_activation.py backend/tests/runtime/test_runtime_orchestration.py -k 'paper_attempt_safety_truth_table or activation_eligibility_uses_the_terminal_safety_matrix or unsafe_outcome_fences_account_observation or terminal_not_run_outcome_reaches_fresh_account_observation or repeated_runtime_keeps_filled_history_separate_from_fresh_entry_gate'
→ 29 passed, 53 deselected
```

The focused R005 startup capability/OANDA selection passed:

```text
uv run pytest -q backend/tests/runtime/test_runtime_orchestration.py backend/tests/test_runtime.py backend/tests/integrations/test_oanda_execution_capability.py
→ 76 passed
```

These fresh selections found no R004 terminal-outcome or R005 non-MT4
capability regression. The immutable R005 canonical validation is `PASS`. The
older R004 canonical validation remains marked `FAIL` for its then-unavailable
dedicated database and broad changed-file Pyright gate; its deterministic
functional evidence is green in this fresh pass, and that artifact was not
changed here.

## Checks and results

| Check | Command/result |
| --- | --- |
| R006 deterministic precision/migration assertions | **6 passed** |
| R006 exact PostgreSQL replay/round-trip selection | **4 passed, 1 deselected** |
| R006 complete repository/migration integration files | **6 passed** |
| R004 focused functional regressions | **29 passed, 53 deselected** |
| R005 focused functional/OANDA regressions | **76 passed** |
| Dedicated migration cycle | **passed**, upgrade → downgrade `0022_paper_persistence` → upgrade |
| Dedicated Alembic current | **0023_paper_runtime_activation (head)** |
| Dedicated Alembic check | **No new upgrade operations detected** |
| Changed Python Ruff format/check | **36 files passed**; all formatted, all checks passed |
| Changed implementation/migration Pyright | **18 files, 0 errors, 0 warnings, 0 informations**; documented `backend/api/app.py` baseline excluded |
| Broad repository Pyright | **2,987 errors**; documented repository baseline, not a product finding |
| Git whitespace | **passed** for tracked and untracked files via `git diff --check` and no-index checks |

## Findings and limitations

1. **No R006 product finding.** Exact PostgreSQL values, loaded `RiskConfig`,
   replay/conflict identity, migration shape, and migration reversibility all
   passed.
2. **Tooling limitation only:** `uv run pyright backend` remains non-clean at
   2,987 errors, consistent with the documented repository-wide baseline. The
   changed implementation/migration slice is clean; no broad Pyright baseline
   diagnostic is attributed to R006.
3. An initial read-only `alembic current` invocation supplied only
   `ATLAS_TEST_DATABASE_URL`; the CLI selected the configured non-dedicated
   database and reported `0020_fix_snapshot_guard`. It was excluded from
   evidence and did not mutate that database. All authoritative migration
   checks and upgrade/downgrade operations were rerun with both
   `ATLAS_TEST_DATABASE_URL` and `ATLAS_DATABASE_URL` explicitly set to the
   dedicated `atlas_freeze07_test` database.
4. Full repository deterministic/integration suites were not part of this
   focused R006 command set and are not claimed as passed. The required exact
   R006 integration files and focused R004/R005 regressions are recorded above.

## Validation receipt

- **Verdict:** `PASS`
- **R006:** exact Decimal request/domain/model persistence, PostgreSQL
  round-trip, loaded `RiskConfig`, same-ID replay, changed-risk conflict,
  old-scale reproduction, migration cycle, current, and check all passed.
- **R004/R005:** focused safety/repeated-runtime and startup capability
  regressions passed; no cross-remediation functional regression observed.
- **Capital safety:** No credentials, activation, real OANDA request, broker
  mutation, PAPER, LIVE, or capital-capable action was performed.
- **Files changed by this validation:** this `VALIDATION.md` only.
