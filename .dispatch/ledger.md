# Dispatch Progress Ledger

Feature: 02 — Core Infrastructure
Branch: feature/02-core-infrastructure

Task 1: complete (commit 8527216, review clean)
Task 2: complete (commits 9cae8d3..5f8fb43, review clean)
Task 3: complete (commits 39bc354..0789915, review clean)
Task 4: complete (commit 5db857a, review clean)
Task 5: complete (commits 3cc6b0e..502040f, review clean)
Task 6: complete (commits c269bf1..411ceaf, review clean)
Final review: conditional pass; five-slice scope ready, Docker/Compose validation pending in Codespaces

## BotSupervisor — feature/02-bot-supervisor

Task 1: complete (commits 1c7f6be..7ce8a44, review clean)
Task 2: complete (commits f0c7ec3..640849d, review clean)
Task 3: complete (commit d6fe996, review clean)
Task 4: complete (commits 980a005..3f862cb, review clean)
Task 5: complete (commits 0dc4ac8..0755a99, review clean)
Final review: conditional pass at 3f862cb; live PostgreSQL/Codespaces verification pending

## Reproducible Development Dependencies — chore/reproducible-dev-dependencies

Task 1: complete (commits 0c3f9e4..78bbc82, review clean)
Task 2: complete (report-only task, review clean)
Task 3: complete (commit 9e25484, review clean with pre-existing lint-config concern)
Final review: conditional pass; Docker/Codespaces validation and frontend lint configuration remain environment/tooling gaps

## Next.js 16 Upgrade — chore/next16-upgrade

Task 1: complete (commit de12636, review clean with residual audit/Node-runtime concerns)
Task 2: complete (commits 07debb5..cf9c624, review clean)
Final review: pending

## Lease/Worker-Ownership Removal — chore/next16-upgrade (uncommitted)

All 9 tasks complete. Summary of changes:
- Task 1 — Inventory: complete (exploration scan across API, supervisor, repos, models)
- Task 2 — Simplify: `LeaseRecord`, `LeaseRepository` protocol, all claim/renew/release
  methods removed from SQLAlchemy and in-memory repositories; `BotRun` model dropped
  (migration 004); supervisor heartbeat, `worker_id`, ownership tracking removed
- Task 3 — Cancellation hang: `_bot_lock` changed from `@asynccontextmanager` to explicit
  `acquire()`/`release()` to fix a deadlock
- Task 4 — Assertion fix: test expectation updated for post-lease semantics
- Task 5 — Verification: 47/47 targeted tests pass, Ruff clean, mypy clean
- Task 6 — Static checks: Ruff + mypy clean
- Tasks 7-9 — Docs, review, fix: 6 canonical files updated; Tier 2 review findings
  (fixture isolation, migration downgrade UC, stale docstring) fixed; follow-up PASS.
  Bounded verification 32/32 pass, Ruff clean. No unbounded suites run (previous hangs).
