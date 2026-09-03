# R005 — Non-MT4 startup capability proof

- **Status:** `PASS`
- **Role:** `REVIEW`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin:** Original `REVIEW.md` `IMPORTANT-02`
- **Review mode:** Independent review of the complete corrected workstream after the approved R004–R006 batch.

## Decision

`PASS`. The corrected R004–R006 batch closes the three original IMPORTANT
product blockers without weakening the approved PAPER 06 safety boundaries. No
unresolved CRITICAL, IMPORTANT, or MINOR product finding remains. No R007 is
authorized or required.

## Review scope

- Inspect the original finding, PLAN/ARCHITECTURE, R004–R006 BUILD and validation evidence, implementation diff, and relevant OANDA/PAPER 05 contracts.
- Specifically judge non-MT4 proof before `RUNNING`, exact configured account and provider semantics, invalid/unavailable fail-closed behavior, bounded read-only startup, shared AccountProperties reader, and absence of new runtime mutation authority.
- Also inspect the R004 unsafe truth/flatness separation, R006 exact Decimal round trip/schema/replay, migration history, and all combined validation limitations.
- No application/test/evidence edits beyond this assigned review artifact; no credentials, activation, real OANDA request, broker mutation, PAPER, or LIVE operation.

## Findings

### CRITICAL

None.

### IMPORTANT

None.

### MINOR

None. The repository-wide Pyright baseline and the historical validation
environment/static-gate limitations are tooling/evidence limitations, not
product findings against this corrected batch.

## Evidence

### R005 — non-MT4 startup capability proof

- `PaperRuntimeOrchestrator._start_active_activation` calls
  `_read_startup_capability()` before the full Account Details observation and
  before the guarded transition to `RUNNING`.
- `_read_startup_capability()` delegates without inspecting provider payloads.
  `OandaPracticeAccountPropertiesReader` uses the Practice-only OANDA base URL,
  performs a read-only `GET /v3/accounts`, requires exactly one match for the
  configured account, validates the account ID, and rejects non-null
  `mt4AccountID`.
- MT4-associated, missing, mismatched, malformed, and unavailable capability
  facts fail closed with bounded lifecycle/reason codes. Temporary 503 failure
  remains `STARTING`/`WAITING_PROVIDER`; invalid normalized facts become
  `BLOCKED`/`STARTUP_CAPABILITY_INVALID`. Account Details is not read until
  capability proof succeeds.
- Production composition creates one normalized capability reader and shares
  that same instance with PAPER 05 preparation. Runtime orchestration has no
  direct OANDA mutation requester; mutation remains behind PAPER 05 durable
  execution.

### R004 regression

- `is_unsafe_paper_attempt` and the SQL predicate agree: `REJECTED`,
  `CANCELLED`, and `FILLED_PROTECTED` with `NOT_RUN` are safe for a fresh
  observation, while UNKNOWN, protection-incomplete, unresolved/conflicted,
  missing, and malformed truth remains unsafe.
- Fresh account truth still governs current flatness. Known attributable
  LONG/SHORT exposure advances Strategy read-only without Risk or a new entry;
  a later fresh FLAT/zero-pending observation is required before opening.

### R006 regression

- Request, domain, model, PostgreSQL load, `RiskConfig`, exact same-ID replay,
  and changed-risk conflict preserve Decimal values including
  `0.12345678901` and `0.00000000001`.
- The model and migration use unconstrained exact PostgreSQL `NUMERIC`, with a
  linear `0022_paper_persistence` → `0023_paper_runtime_activation` history.

## Checks and evidence

- Focused runtime/activation/OANDA/API/Risk/migration tests: **124 passed**, 1
  existing Starlette/httpx deprecation warning.
- Dedicated PAPER 06 PostgreSQL migration/repository/completion/ownership suite:
  **17 passed** against `atlas_freeze07_test`.
- Dedicated PAPER 05 repository and OANDA reconciliation regressions: **10 + 11
  passed** when rerun independently after an initial DB-lock contamination from
  an orphaned timed-out integration process; the contaminated invocation is not
  used as evidence.
- Changed implementation Ruff format/check: passed; focused Pyright:
  **0 errors, 0 warnings, 0 informations**.
- Dedicated Alembic `current`: `0023_paper_runtime_activation (head)`;
  `alembic check`: **No new upgrade operations detected**.
- `git diff --check`: passed.
- Combined validation evidence records the full deterministic backend suite as
  **1108 passed, 4 skipped, 115 deselected**, with the known repository-wide
  Pyright baseline documented separately.

## Limitations

- No real credentials, provider request, activation, PAPER/LIVE operation, or
  broker mutation was performed.
- Repository-wide Pyright remains non-clean because of the documented baseline;
  the affected implementation/migration slice is clean.
- A prior combined integration attempt was invalidated by concurrent/orphaned
  database-test cleanup and deadlocked; serial/isolated reruns passed and are
  the evidence used above.

## Review receipt

- **Verdict:** `PASS`
- **CRITICAL findings:** None
- **IMPORTANT findings:** None
- **MINOR findings:** None
- **R004:** terminal-outcome safety and fresh flatness separation closed.
- **R005:** exact non-MT4 capability proof precedes `RUNNING` and remains
  read-only/shared with P05.
- **R006:** exact Decimal persistence, replay/conflict identity, and migration
  lifecycle closed.
- **Capital safety:** No credentials, activation, PAPER/LIVE operation, real
  OANDA request, or broker mutation occurred.
- **Files changed by this review:** this `REVIEW.md` only.
