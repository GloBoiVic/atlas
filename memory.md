# Memory — Atlas Foundation and Corrected Backend Layout

Last updated: 2026-08-12

## What was built

- **Phase 0 — Project Foundation (COMPLETE, APPROVED 2026-08-12):** repository foundation with no trading functionality yet. Root manifests and lockfiles (`pyproject.toml`, `uv.lock`, `package.json`, `package-lock.json`); typed `ATLAS_` config with secret-safe logging; SQLAlchemy 2 + psycopg 3 + Alembic empty baseline (single head `0001_phase_0_baseline`); FastAPI `/health/live` + `/health/ready` (sanitized 503 when DB down); `atlas-runtime` process (`--check` exit codes 0/1/2, clean signal shutdown); Next.js 16 frontend (single page, strict TS, Tailwind v4); pytest (unit + guarded PostgreSQL integration), Vitest, Playwright e2e; quality gates (Ruff, Pyright strict, ESLint, Prettier, tsc, build); root README. All 21 acceptance criteria PASS.
- **Flat Backend — corrective package layout (COMPLETE, APPROVED 2026-08-12):** `backend/` is now the sole Python import package, directly containing application source plus retained `backend/tests/`. Repository-root `atlas/` source package removed; `backend/atlas/` forbidden. Distribution `atlas-platform`, API/runtime/health contracts, migration history, and frontend unchanged. `context/architecture/repository-structure.md` corrected to match.

## Decisions made

- **Flat package layout:** `backend/` is the regular import package at repository root — no `src/`, no shims, no `PYTHONPATH`, no `sys.path` mutation, no `extraPaths`. Namespace is `backend.*`; root `atlas.*` and `backend.atlas.*` are explicitly invalid. This is now an architectural invariant documented in `context/architecture/repository-structure.md`.
- **Execution namespace (locked):** console entry `atlas-runtime = backend.runtime.main:main`; Uvicorn factory `backend.api.app:create_app`; Alembic `script_location = backend/persistence/migrations` (single head `0001_phase_0_baseline`); pytest testpaths `backend/tests`; Pyright include `backend`.
- **No `context/index.md` exists.** Architecture sources are read directly from `context/architecture/` (domain-model.md, repository-structure.md, tech-stack.md, runtime-model.md, safety-model.md, strategy-contract.md, market-data-model.md, accounting-model.md, architecture.md, database.md) plus `context/product/`, `context/roadmap/`, `context/features/`, `context/design/design.md`, `context/development/`. Do not create an index without being asked.
- **Dispatch history policy:** pre-existing `dispatch/` artifacts are immutable (SHA-256 checksum-verified baseline); `MODEL-LOG.md` is the sanctioned append-only bookkeeping target. Completion records live in `dispatch/COMPLETED.md` (preserve it; do not delete or rewrite).
- Credentials follow `.env.example` shape only; never persist or log real secrets.

## Problems solved

- **Root `atlas/` → `backend/` move without breakage:** the corrective workstream (FB-01..FB-07) moved application source into `backend/`, flipped all imports/patch targets/subprocess snippets to `backend.*`, and re-verified locked reinstall, wheel contents, outside-repository import, and one Alembic head — no shims or behavior changes. If imports ever resolve to a nonexistent `atlas.` path, the fix is `backend.` (no PYTHONPATH tricks).
- **Append-only MODEL-LOG verification pattern:** baseline SHA-256 prefix (through row 21 = `a8952623…`) proves later rows were appended, never rewritten. Reuse this pattern for any future dispatch bookkeeping.
- **Wheel includes retained `backend/tests/`** — recorded as a fact (M1), not a defect; no packaging exclusion was added per blueprint. Do not "fix" this without explicit instruction.

## Eureka moments

- The flat layout correction was treated as a **verification problem, not just a move**: the whole workstream's value was the independent re-run of every gate against the real environment (process, PostgreSQL, wheel, outside-repo import, checksums). Independent review (reviewer separate from builder) is the project's completion gate — never skip it.

## Current state

- Phase 0 and Flat Backend workstreams are **closed and APPROVED** (recorded in `dispatch/COMPLETED.md`). No trading functionality exists yet.
- All gates green as of 2026-08-12: ruff + pyright strict clean; 15 unit + 2 guarded integration tests pass; Alembic one head at `0001_phase_0_baseline`; API health contracts exact; runtime exit codes 0/1/2; frontend `npm run check:web` and Playwright e2e pass.
- Environment facts: uv 0.12.3, Python 3.13.3, PostgreSQL 18.4, Node v24.18.0 (deviation from blueprint's Node 22 LTS — documented O2, all gates pass).
- **Remaining non-blocking observations:**
  - O1: Playwright webserver logs a Next.js dev HMR `allowedDevOrigins` warning (cosmetic; optional future `allowedDevOrigins: ['127.0.0.1']`).
  - O2: Node v24.18.0 vs blueprint Node 22 LTS — documented, no action.
  - O3: one StarletteDeprecationWarning in pytest (httpx + starlette.testclient); blueprint pins `httpx<1`; the doc suggests `httpx2` — not fixed, do not change the pin without instruction.
  - M1: wheel includes retained backend tests (recorded fact). M2: pre-existing env-only warnings. M3: `rg` unavailable — use `grep -rn`/`shasum` equivalents.

## Next session starts with

1. **Phase 1 planning — nothing more.** The next workstream is Phase 1 planning, which **must start with Explore → Architect → explicit human confirmation** before any implementation. Do not begin building.
2. Read `AGENTS.md` (trading invariants, domain language, context hierarchy, precedence rules) and the architecture docs above; then load the specific feature docs for whatever Phase 1 slice the human confirms.
3. Likely Phase 1 candidates per scope (do not assume): historical data (1m EUR/USD), reference Strategy (EMA Sweep Engulfing, 15m), Experiments pipeline — pick only after confirmation.

## Open questions

- Phase 1 slice/scope is not yet defined — requires human decision after Explore/Architect.
- Whether to address O1 (`allowedDevOrigins`) and O3 (`httpx2`/StarletteDeprecationWarning) in a later session — both explicitly non-blocking.
- `context/index.md` has never been created; decide with the human whether one is wanted.

---

_Security note: this file intentionally contains no credentials, database URLs, or secret values. `.env` and `.env.example` are referenced only as file names._
