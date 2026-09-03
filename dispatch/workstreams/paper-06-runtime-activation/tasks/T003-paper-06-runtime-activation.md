# T003 — Runtime ownership

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Depends on:** T001, T002
- **Owned artifact:** this file

## Objective

Implement one dedicated pinned PostgreSQL advisory-lock runtime owner with durable ownership evidence and owner-generation guards.

## Required boundaries

- Acquire the fixed documented advisory key through `pg_try_advisory_lock` on a dedicated lifetime connection, never a transient pooled Session.
- Write/advance durable ownership evidence only after lock acquisition; heartbeat is audit evidence only.
- Fence cycle reservation, ENTRY claims, dependent claims, and post-claim dispatch after owner loss.
- Treat guarded zero-row updates as ownership loss; never transfer/release/reacquire claims.
- A loser performs no cycle, broker read, or mutation.

## Evidence required

- Dedicated PostgreSQL concurrency tests with two owners, stale heartbeat, lock release after connection death, owner-generation guards, and zero-row loss behavior.

## Completion receipt

Implemented the dedicated PAPER runtime owner.  A successful acquisition uses
`pg_try_advisory_lock` on one pinned SQLAlchemy PostgreSQL connection, commits
that lock transaction, and writes the durable ownership projection only after
the lock is held.  Losing sessions close their candidate connection without a
durable write.  Owner operations verify the live session lock and delegate
owner-id/owner-generation guards to the runtime repository; zero-row guard
loss permanently fences the owner object.  Explicit close unlocks before the
pinned connection is returned to the pool, while connection invalidation
retains PostgreSQL's session-death release behavior.

### Files changed

- `backend/runtime/ownership.py`
- `backend/runtime/__init__.py`
- `backend/tests/integration/test_runtime_ownership.py`

### Checks and evidence

- Dedicated PostgreSQL `atlas_t003_test`: runtime ownership, runtime repository,
  and migration integration tests: `9 passed`.
- Evidence covers concurrent two-owner acquisition with exactly one winner,
  stale heartbeat non-takeover, explicit unlock, connection invalidation and
  successor generation advancement, and zero-row owner-generation loss.
- Full non-integration/non-external backend suite: `986 passed, 4 skipped,
  103 deselected` (existing warnings only).
- Changed-slice Ruff format/check and Pyright: passed.
- Alembic `current`: `0023_paper_runtime_activation (head)`; Alembic `check`:
  no new upgrade operations detected.
- `git diff --check`: passed.
- No OANDA calls, credentials, PAPER activation, or broker mutation were used.

### Concerns / handoff

- Runtime orchestration must use `PaperRuntimeOwner`'s pinned connection and
  guarded methods; it must not acquire the advisory lock through a transient
  pooled Session or use heartbeat age as takeover authority.
