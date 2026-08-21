# Memory — Atlas Phase 3 First Historical Trade

Last updated: 2026-08-21

## What was built

- **Phase 0 — Project Foundation (COMPLETE, APPROVED 2026-08-12):** repository foundation with no trading functionality yet. Root manifests and lockfiles (`pyproject.toml`, `uv.lock`, `package.json`, `package-lock.json`); typed `ATLAS_` config with secret-safe logging; SQLAlchemy 2 + psycopg 3 + Alembic empty baseline (single head `0001_phase_0_baseline`); FastAPI `/health/live` + `/health/ready` (sanitized 503 when DB down); `atlas-runtime` process (`--check` exit codes 0/1/2, clean signal shutdown); Next.js 16 frontend (single page, strict TS, Tailwind v4); pytest (unit + guarded PostgreSQL integration), Vitest, Playwright e2e; quality gates (Ruff, Pyright strict, ESLint, Prettier, tsc, build); root README. All 21 acceptance criteria PASS.
- **Flat Backend — corrective package layout (COMPLETE, APPROVED 2026-08-12):** `backend/` is now the sole Python import package, directly containing application source plus retained `backend/tests/`. Repository-root `atlas/` source package removed; `backend/atlas/` forbidden. Distribution `atlas-platform`, API/runtime/health contracts, migration history, and frontend unchanged. `context/architecture/repository-structure.md` corrected to match.
- **Phase 1 — Reference Strategy (COMPLETE, REVIEW APPROVED):** implementation commit `eed18db` and documentation commit `b6d9a31`, both on `main`. The reference strategy is EUR/USD MID on 15m, with immutable persisted `StrategyVersion` records. The reference calculation uses EMA-100 with an SMA seed followed by recursive alpha `2/101`, ATR-14 using Wilder smoothing without fabricating the first true range, and the W1–W5 reference window. Trend is reference-only; state safety gates and completed-candle/no-lookahead rules are enforced.
- **Phase 2 — Historical Data to DatasetSnapshot (COMPLETE, REVIEW PASS 2026-08-21):** EUR/USD OANDA Practice completed M1 BID/MID/ASK ingestion, coverage/gap validation, immutable correction variants, deterministic snapshot-only M15 derivation, immutable DatasetSnapshot persistence, and the narrow `atlas-data` CLI/operator documentation. Acceptance evidence and deferred Minors are recorded in `dispatch/COMPLETED.md`.
- **Phase 3 — First Historical Trade (COMPLETE, REVIEW PASS 2026-08-21):** deterministic persisted EUR/USD LONG and SHORT Experiments through Strategy → TradeIntent → RiskDecision → Order → Fill → Position → Trade, with immutable snapshot provenance, no-lookahead clocking, centralized Risk, pure simulated execution, Fill-authoritative exposure, sanitized fail-closed failures, and `PHASE3_OPEN_CHECKPOINT_V1`. Phase 4/API/UI/broker/runtime behavior remains excluded.

## Decisions made

- **Flat package layout:** `backend/` is the regular import package at repository root — no `src/`, no shims, no `PYTHONPATH`, no `sys.path` mutation, no `extraPaths`. Namespace is `backend.*`; root `atlas.*` and `backend.atlas.*` are explicitly invalid. This is now an architectural invariant documented in `context/architecture/repository-structure.md`.
- **Execution namespace (locked):** console entry `atlas-runtime = backend.runtime.main:main`; Uvicorn factory `backend.api.app:create_app`; Alembic `script_location = backend/persistence/migrations` (single head `0001_phase_0_baseline`); pytest testpaths `backend/tests`; Pyright include `backend`.
- **No `context/index.md` exists.** Architecture sources are read directly from `context/architecture/` (domain-model.md, repository-structure.md, tech-stack.md, runtime-model.md, safety-model.md, strategy-contract.md, market-data-model.md, accounting-model.md, architecture.md, database.md) plus `context/product/`, `context/roadmap/`, `context/features/`, `context/design/design.md`, `context/development/`. Do not create an index without being asked.
- **Dispatch history policy:** pre-existing `dispatch/` artifacts are immutable (SHA-256 checksum-verified baseline); `MODEL-LOG.md` is the sanctioned append-only bookkeeping target. Completion records live in `dispatch/COMPLETED.md` (preserve it; do not delete or rewrite).
- Credentials follow `.env.example` shape only; never persist or log real secrets.
- The reference Strategy is deliberately narrow: EUR/USD MID, 15m, EMA-100, ATR-14, and W1–W5. 5m and 1m strategy timeframes are deferred.
- `StrategyVersion` is immutable after persistence. The strategy remains reference-only and does not own Risk or execution; safety gates must fail closed rather than fabricate state.
- Phase 2 is backend-plus-CLI only; Experiment execution, Risk, orders, live trading, streaming, scheduling, API, and UI remain deferred.
- Phase 3 uses exactly eight approved new tables in migration `0004_phase_3_first_trade`; forward migration `0005_phase_3_failure_persistence` adds immutable terminal failure facts. No TradingAccount, Deployment, RiskProfile, OrderEvent, equity-history, SystemEvent, or generalized infrastructure was added.
- OBS-2 was resolved with test-only PostgreSQL integration isolation. OBS-1 (NY-calendar/partial-break warmup coupling) and OBS-3 (runner Pyright hygiene) remain non-blocking follow-ups.

## Problems solved

- **Root `atlas/` → `backend/` move without breakage:** the corrective workstream (FB-01..FB-07) moved application source into `backend/`, flipped all imports/patch targets/subprocess snippets to `backend.*`, and re-verified locked reinstall, wheel contents, outside-repository import, and one Alembic head — no shims or behavior changes. If imports ever resolve to a nonexistent `atlas.` path, the fix is `backend.` (no PYTHONPATH tricks).
- **Append-only MODEL-LOG verification pattern:** baseline SHA-256 prefix (through row 21 = `a8952623…`) proves later rows were appended, never rewritten. Reuse this pattern for any future dispatch bookkeeping.
- **Wheel includes retained `backend/tests/`** — recorded as a fact (M1), not a defect; no packaging exclusion was added per blueprint. Do not "fix" this without explicit instruction.
- **Reference Strategy verification:** 81 non-integration tests plus 5 PostgreSQL integration tests pass; Ruff, Pyright, and Alembic checks pass.
- **Phase 2 verification:** integration 14/14 including DB CLI; Ruff format/check; Pyright; 126 non-integration/non-external tests; Alembic current/check; and one bounded OANDA Practice historical smoke test with no account/trading/live/DB calls.
- **Phase 3 verification:** LONG/SHORT golden flows, migration cycle, failure persistence, Fill application, snapshot reads, quality checks, and semantic reruns passed. Final sequential full-suite rechecks each yielded 170 passed and 1 skipped; integration-only yielded 18 passed.

## Eureka moments

- The flat layout correction was treated as a **verification problem, not just a move**: the whole workstream's value was the independent re-run of every gate against the real environment (process, PostgreSQL, wheel, outside-repo import, checksums). Independent review (reviewer separate from builder) is the project's completion gate — never skip it.
- The Reference Strategy is complete only when its indicator seeds, window semantics, no-lookahead behavior, persisted immutability, and safety gates are explicit and independently reviewable; the review was approved.

## Current state

- Phase 0, Flat Backend, Phase 1 Reference Strategy, Phase 2 Historical Data to DatasetSnapshot, and Phase 3 First Historical Trade are **closed and APPROVED/PASS** (recorded in `dispatch/COMPLETED.md`).
- Phase 1 verification is green: 81 non-integration tests plus 5 PostgreSQL integration tests; Ruff, Pyright, and Alembic checks pass.
- `main` was clean at the last verification. The feature worktree is retained; there is no automatic cleanup.
- Environment facts: uv 0.12.3, Python 3.13.3, PostgreSQL 18.4, Node v24.18.0 (deviation from blueprint's Node 22 LTS — documented O2, all gates pass).
- **Remaining non-blocking observations:**
  - O1: Playwright webserver logs a Next.js dev HMR `allowedDevOrigins` warning (cosmetic; optional future `allowedDevOrigins: ['127.0.0.1']`).
  - O2: Node v24.18.0 vs blueprint Node 22 LTS — documented, no action.
  - O3: one StarletteDeprecationWarning in pytest (httpx + starlette.testclient); blueprint pins `httpx<1`; the doc suggests `httpx2` — not fixed, do not change the pin without instruction.
  - M1: wheel includes retained backend tests (recorded fact). M2: pre-existing env-only warnings. M3: `rg` unavailable — use `grep -rn`/`shasum` equivalents.
  - Phase 2 Minors: wrong-provider coverage; explicit timeframe mapping; serialization/docstring cleanup; full integrity-summary shape; speculative aliases; hardcoded M1 header; idempotent snapshot lookup coverage; service error-path and byte-serialization coverage; summary-key casing; generic partial-fetch failure class.
  - Phase 3 follow-ups: OBS-1 NY-calendar/partial-break warmup coupling and OBS-3 runner Pyright errors. Both are non-blocking.

## Next session starts with

1. Phase 3 is closed and recorded in `dispatch/COMPLETED.md`; preserve the feature branch and uncommitted task context unless explicitly instructed otherwise.
2. Any future work starts by reviewing the Phase 3 record and the two non-blocking follow-ups; do not expand into Phase 4 without approval.
3. Keep 5m and 1m strategy timeframes deferred; do not generalize beyond approved scope without confirmation.

## Open questions

- Whether and when to address Phase 3 OBS-1 and OBS-3; neither blocks the completed Phase 3 slice.
- Whether to address O1 (`allowedDevOrigins`) and O3 (`httpx2`/StarletteDeprecationWarning) in a later session — both explicitly non-blocking.
- `context/index.md` has never been created; decide with the human whether one is wanted.

---

_Security note: this file intentionally contains no credentials, database URLs, or secret values. `.env` and `.env.example` are referenced only as file names._
