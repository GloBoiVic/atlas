# R005 — Non-MT4 startup capability proof

- **Status:** `PASS`
- **Role:** `VALIDATE`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **HEAD:** `0960191344595cf059cd99cb5bfb5ac6ce930dcd` (combined dirty BUILD state)
- **Origin:** Original `REVIEW.md` `IMPORTANT-02`
- **Validation mode:** Fresh independent validation of the combined current HEAD after the approved R004–R006 BUILD batch.

## Decision

`PASS`. R005 startup capability proof is closed, and the independent combined
pass kept R004 and R006 green. All product/runtime checks requested for this
batch passed. Repository-wide Pyright remains a known pre-existing typing
baseline limitation; the changed implementation batch is clean separately.

## Scope and safety

- Verified repository root `/Users/vike/Desktop/atlas`, branch
  `solo/paper-06-runtime-activation`, and HEAD before and after validation.
- Used the dedicated database explicitly for every PostgreSQL check:
  `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test'`.
  It was upgraded from 0022 to head, downgraded to 0022, and upgraded to head
  again. No non-dedicated database was used for integration evidence.
- Read the canonical `ACTIVE.md`, `PLAN.md`, `ARCHITECTURE.md`, original
  `REVIEW.md`/`VALIDATION.md`, T001–T008 receipts, R004–R006 BUILD/validation
  packets, PAPER 05 validation, DOMAIN.md, README.md, and directly affected
  implementation/tests.
- No real credentials, activation, real OANDA request, broker mutation, PAPER,
  LIVE operation, Risk-policy change, or Git-history operation occurred.
  Provider tests used deterministic fakes and `httpx.MockTransport`.

## R005 acceptance evidence

### Exact non-MT4 proof and ordering

Source inspection confirms `PaperRuntimeOrchestrator._start_active_activation`
calls `_read_startup_capability()` before `_read_observation()` and before the
guarded transition to `RUNNING`. `_read_startup_capability()` delegates to the
injected normalized reader and does not inspect or reinterpret provider fields.

`OandaPracticeAccountPropertiesReader` performs one read-only `GET /v3/accounts`.
Its existing normalizer requires exactly one match for the server-configured
account, a valid OANDA Practice account ID, and `mt4AccountID is None`.

The focused test `test_startup_proves_non_mt4_capability_before_running` passed
with event order `capability → account`; it asserted the resulting lifecycle is
`RUNNING` and `runtime.running is True`. The R005 runtime/OANDA batch passed
`76` tests.

### Bounded fail-closed cases

| Case | Evidence | Result |
| --- | --- | --- |
| Exact configured non-MT4 AccountProperties | startup ordering test; one GET | `RUNNING` only after proof |
| MT4-associated (`mt4AccountID`) | startup parameterized test | `BLOCKED / STARTUP_CAPABILITY_INVALID`; no Account Details read |
| Missing/empty account list | startup parameterized test | same bounded block |
| Mismatched configured account | startup parameterized test | same bounded block |
| Invalid account ID / malformed facts | startup and OANDA normalizer tests | same bounded block |
| Temporary provider failure (HTTP 503) | startup retry test | 3 bounded capability attempts; `STARTING / WAITING_PROVIDER / STARTUP_READ_UNAVAILABLE`; no Account Details read |

The OANDA capability suite also passed invalid AccountProperties shape/type
coverage. Starting with no activation remained idle and made no provider read.

### Shared reader and mutation boundary

Production composition constructs one `OandaPracticeAccountPropertiesReader`,
passes it as the runtime `capability_reader`, and passes the same object into
PAPER 05 durable execution as its account-properties reader. The composition
test asserted object identity. The reader is backed by
`OandaObservationRequester`, whose only provider operation here is bounded
authenticated `client.get`; it has no POST/PUT seam. Runtime orchestration
delegates any capital-capable operation to the existing PAPER 05 durable
execution authority and does not construct or call an OANDA mutation requester.

## R004 regression evidence

The exact R004 safety matrix and fresh-account/repeated-runtime tests passed:
`29 passed` for the named matrix/regression selection and `127 passed` for the
full runtime plus runtime-entrypoint suite. This independently confirms:

- `REJECTED`, `CANCELLED`, and `FILLED_PROTECTED` with `NOT_RUN` are safe for a
  fresh account observation;
- `UNKNOWN`, `FILLED_PROTECTION_INCOMPLETE`, unresolved/conflicted, missing, and
  malformed outcome/status truth remains unsafe;
- historical `FILLED_PROTECTED` does not prove current flatness;
- known attributable LONG/SHORT exposure advances Strategy read-only without
  Risk or a new entry, while a later fresh FLAT/zero-pending observation is
  required before a new opening.

Dedicated runtime completion/repository/ownership integration evidence also
passed, and PAPER 05 execution/reconciliation regressions remained green.

## R006 regression evidence

The focused Risk/activation/API/migration batch passed `29` tests (one existing
FastAPI/httpx deprecation warning). Dedicated repository tests passed exact
round trips for `0.01`, `0.12345678901`, and `0.00000000001`, exact loaded
`RiskConfig`, same-ID exact replay, and changed-risk identity conflict. The
dedicated migration assertion observed PostgreSQL `NUMERIC` with
`numeric_precision IS NULL` and `numeric_scale IS NULL`.

A read-only PostgreSQL cast reproduced the former loss and the corrected
representation:

```text
NUMERIC(30,10): 0.1234567890, 0E-10
NUMERIC:        0.12345678901, 1E-11
```

## Checks and results

| Check | Command/result |
| --- | --- |
| Focused R005 startup/account/OANDA | `uv run pytest -q backend/tests/runtime/test_runtime_orchestration.py backend/tests/test_runtime.py backend/tests/integrations/test_oanda_execution_capability.py` — **76 passed** |
| Focused R004 safety/runtime | named truth-table/fresh-observation selection — **29 passed**; full `backend/tests/runtime backend/tests/test_runtime.py` — **127 passed** |
| Focused R006 Risk/activation precision | **29 passed**, 1 existing warning |
| PAPER 05 execution/reconciliation + OANDA unit regressions | **68 passed** |
| Full deterministic backend | `pytest -m 'not integration and not external'` — **1108 passed, 4 skipped, 115 deselected**, 4 existing warnings |
| Dedicated PAPER 06 integration suite | `test_runtime_migration.py`, `test_runtime_repository.py`, `test_runtime_completion.py`, `test_runtime_ownership.py` — **17 passed** |
| Dedicated PAPER 05/OANDA integration regressions | `test_paper_execution_repository.py`, `test_oanda_reconciliation.py` — **21 passed** |
| Ownership/concurrency/STOP unit checks | **10 passed, 109 deselected** |
| Ownership/concurrency/STOP dedicated checks | **7 passed, 4 deselected** |
| Migration cycle | dedicated DB `upgrade head → downgrade 0022_paper_persistence → upgrade head` — passed |
| Alembic state/check | `current`: `0023_paper_runtime_activation (head)`; `check`: **No new upgrade operations detected** |
| Changed implementation Ruff | 19 implementation/migration files: format **passed**, lint **passed** |
| Changed R004–R006 implementation/migration Pyright slice (excluding the documented `backend/api/app.py` baseline) | **0 errors, 0 warnings, 0 informations** |
| All changed Python Ruff | 36 files: format/check **passed** |
| `git diff --check` | **passed**, including tracked and untracked changed Python/Markdown files |

## Tooling limitation (not a product finding)

The requested broad typing runs remain non-clean due the documented baseline:

- `uv run pyright backend` — **2987 errors**, 0 warnings/informations;
- all currently changed Python files — **123 errors**, concentrated in the
  pre-existing `backend/api/app.py` app-factory typing and test/fake typing in
  `backend/tests/runtime/test_runtime_activation.py` and
  `backend/tests/test_api_paper.py`.

The clean changed implementation/migration Pyright result is reported above
separately. These baseline diagnostics are not attributed to R005, R004, or
R006 and do not change the functional PASS verdict.

The first attempt ran the two dedicated integration groups concurrently against
the same database and produced PostgreSQL deadlock failures from their
overlapping test/migration locks. The groups were then rerun serially against
the explicitly dedicated database and passed (`17` and `21` respectively); the
parallel invocation is not used as product evidence.

## Validation receipt

- **Verdict:** `PASS`
- **R005:** exact non-MT4 proof precedes `RUNNING`; MT4/missing/mismatched/
  invalid/unavailable facts fail closed with bounded reasons; startup remains
  read-only and shares the provider-specific reader with P05.
- **R004:** terminal-outcome safety, fresh account gating, attributable-open
  read-only progression, ownership, and STOP/concurrency regressions passed.
- **R006:** exact Decimal persistence, PostgreSQL round trip/replay/conflict,
  migration cycle, and old-scale read-only reproduction passed.
- **Concerns:** broad repository/test Pyright baseline as documented above; no
  capital-capable or external broker operation was performed.
- **Files changed by this validation:** this `VALIDATION.md` only.
