# Completed Work

---

## 2026-08-02 — Context Normalization Before Feature 03

- Reconciled Atlas context with the actual single-user, single-worker, paper-first platform.
- Reworked persistence guidance around the target native UUID identity, service-owned
  transactions, provider-aware instruments, explicit candle price/volume semantics, dataset
  identity, and an explicit Trade lifecycle.
- Clarified Binance Spot as the first concrete provider and OANDA as deferred, including their
  differing kline/candle formats and live-feed semantics.
- Separated historical Feature 03 responsibilities from live streaming Feature 08 and replay
  responsibilities in Feature 05.
- Documented typed event payload contracts as required targets while recording the current
  implementation gap; reserved production mode remains consistently documented as gated.
- Updated dependent feature files, roadmap, coding standards, and library guidance. No
  application implementation was performed. Feature 03 implementation planning remains next.

The canonical record of completed dispatch work. One-off task briefs and reports are
deleted after their summaries are captured here; full detail remains recoverable from
git history.

---

## 2026-08-02 — Dispatch Cleanup

- Consolidated `.dispatch/` into a single `COMPLETED.md` record. Renamed the former
  `ledger.md` to `COMPLETED.md` and updated it with the Feature 03 session state.
- Deleted 32 one-off task brief/report files from the working tree (recoverable from
  git). `.dispatch/` remains gitignored for future artifacts; new dispatch files are
  not tracked.

---

## Feature 03 — Data Layer (in progress)

- **Branch:** `feature/03-data-layer` (created 2026-08-02)
- **Status:** Branch created from `main`; `CURRENT.md` updated. No implementation yet.
- **Next:** DataProvider interface, Candle/Tick/Instrument models, CSV provider,
  historical loader, candle storage pipeline, Binance provider (ccxt), provider registry.

---

## Feature 02 — Core Infrastructure

**Branch(s):** `feature/02-core-infrastructure`, `feature/02-bot-supervisor`,
`chore/next16-upgrade` (lease removal). All tasks complete.

### Feature 02 — Core Infrastructure (6 tasks)

- Task 1 — Shared `AccountMode` moved to `backend/core/account_mode.py`
  (commit `8527216`).
- Task 2 — Typed EventBus in `backend/core/events.py` with sequential awaited
  delivery, event metadata, failure recording, and bot pause callback
  (commits `9cae8d3..5f8fb43`).
- Task 3 — Clock abstraction: `Clock`, `LiveClock`, `SimulationClock`
  (commits `39bc354..0789915`).
- Task 4 — Pydantic v2 Settings + YAML strategy/risk/broker config with
  `${VAR}` expansion and strict paper/testnet/production validation (commit `5db857a`).
- Task 5 — Circuit breaker and composable `retry_async()` in
  `backend/health/circuit_breaker.py` (commits `3cc6b0e..502040f`).
- Task 6 — Structured structlog JSON configuration in `backend/core/logging.py`
  (commit `c269bf1`).
- Final review: conditional pass; five-slice scope ready, Docker/Compose validation
  pending in Codespaces.

### BotSupervisor slice (5 tasks)

- Task 1 — ORM models + migration `002` for `bots`, `bot_runs`, `reconciliation_runs`
  (commits `1c7f6be..7ce8a44`).
- Task 2 — Repository boundaries: protocols, SQLAlchemy, in-memory implementations
  (commits `f0c7ec3..640849d`).
- Task 3 — Runtime protocols: `BotPipeline`, `PipelineFactory`, `Reconciler`
  (commit `d6fe996`).
- Task 4 — `BotSupervisor` implementation: per-bot lock, lease claims, lifecycle
  persistence, reconciliation gating, heartbeat ownership, shutdown (commits `980a005..3f862cb`).
- Task 5 — Worker entrypoint wiring + docs (commits `0dc4ac8..0755a99`).
- Final review: conditional pass; live PostgreSQL/Codespaces verification pending.

### Reproducible development dependencies (3 tasks)

- Task 1 — Lockfiles generated: `uv.lock` (73 packages), `frontend/package-lock.json`
  (342 packages). No manifest changes (commits `0c3f9e4..78bbc82`).
- Task 2 — Local `.venv` installed from `.[dev]`; 150 tests, Ruff, mypy passed
  (report-only task).
- Task 3 — `Dockerfile.frontend` switched to `npm ci`; Codespaces docs updated;
  Docker dev/prod image split deferred (commit `9e25484`).

### Next.js 16 upgrade (2 tasks)

- Task 1 — Next.js 16.2.12 / React 19.2.8 upgrade, ESLint flat config replacing
  `next lint`, standalone output preserved (commit `de12636`).
- Task 2 — Docs/runtime guidance: tech-stack, library-docs, codespaces docs,
  devcontainer Node 20.9, `node:20.9-slim` frontend image (commits `07debb5..cf9c624`).
- Known residual risk: `npm audit` transitive vulnerabilities (PostCSS/sharp); no
  overrides or downgrades applied.

### Lease / worker-ownership removal (9 tasks, commit `8b735ec`)

- Removed cross-worker lease protocol: `LeaseRecord`/`LeaseRepository`, all
  claim/renew/release methods, `BotRun` model (migration `004` drops `bot_runs`),
  supervisor heartbeat/`worker_id`/ownership tracking.
- `_bot_lock` changed from `@asynccontextmanager` to explicit `acquire()`/`release()`
  to fix a cancellation deadlock.
- Single-worker deployment invariant now replaces cross-worker mutual exclusion.
- Verification: 47/47 targeted tests, Ruff clean, mypy clean; bounded 32/32 pass on
  follow-up review cycle.

### Feature 02 final fix

- `config/` copied into API and worker images; `CURRENT.md` and feature file updated
  to mark implemented criteria complete while health monitor stays deferred.
  Verification: 71 tests passed, Ruff/mypy clean (commit `061ddb9` + follow-up).

### Deferred

- Health monitor and orphan-state handling remain deferred (pre-existing).
- Docker/Compose/PostgreSQL validation pending in Codespaces (single Codespace on
  `main`; feature branches checked out inside it for validation).
