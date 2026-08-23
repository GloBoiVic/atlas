# AUDIT — Targeted Review

Scope requested: **local-first / DB / API / runtime / secrets / Strategy / lifecycle / shipping / core-shell**
Method: read-only, CodeGraph-first symbol mapping + targeted file inspection. No edits made.
Date: 2026-08-23
Status: recovered authoritative report (reproduced from misplaced root `AUDIT.md`; citations re-verified against current source).

---

## 1. Security Findings

### Important
- `backend/api/app.py:52` + `frontend/next.config.ts:13-21` — **Entire Atlas API is unauthenticated and unreferenced by any trust boundary, and is proxied by the Next.js server.**
  - Evidence: `create_app` adds no `CORSMiddleware`, no auth dependency, no `TrustedHost`, no rate limiting (only `Depends(session)` DB dependencies in `experiments.py`). FastAPI `FastAPI(title="Atlas API", lifespan=lifespan)` is created with default `docs_url`/`redoc_url` enabled (`/docs` Swagger).
  - `next.config.ts` rewrites `/atlas-api/:path*` → `ATLAS_API_BASE_URL/:path*`, and `allowedDevOrigins` is `undefined` for non-dev builds, so it constrains nothing in production.
  - README (`README.md:88`) binds uvicorn to `127.0.0.1` only; that is the current, documented, local-only posture and is acceptable *if* the surface stays loopback-only.
  - Impact: If either the Next server (`next start` binds `0.0.0.0` by default) or the FastAPI app is bound/exposed beyond loopback, the full unauthenticated API — `POST /api/v1/experiments` (create), `POST /{id}/run` (synchronous, potentially long computation), `GET .../trades` / `.../equity` — becomes reachable with no guard, no rate limit, and no origin restriction. `/docs` also exposes the full contract. This is a shipping/core-shell hardening gap: there is no deployment-time gate preventing accidental network exposure.
  - Validated: confirmed no middleware/auth across `backend/api/`; confirmed rewrite and production-undefined origin allowlist.

### Minor
- `backend/api/app.py:52` — FastAPI interactive docs (`/docs`, `/redoc`) are enabled by default. Harmless on a loopback-only local tool, but if the surface is ever exposed this expands the discoverable attack/service surface. Consider `docs_url=None` unless explicitly needed.

---

## 2. Best-Practices Findings

### Important
- `backend/api/experiments.py:282-290` + `frontend/lib/api-client.ts:78-79` + `frontend/components/experiment-workflow.tsx:1021-1025` — **Long, synchronous Experiment runs outlive the caller's timeout; the client treats timeout as "outcome unknown."**
  - Evidence: `POST /{experiment_id}/run` calls `lifecycle.run(experiment_id)` synchronously in a `def` (threadpool) route; the client `runExperiment` uses an 8,000 ms `AbortController`. `AbortController` only cancels the browser fetch — the server-side run continues and persists.
  - The lifecycle is correctly safe here (durable `RUNNING` claim + row-lock prevents double-run; the terminal state remains authoritative via subsequent GET), and the timeout is handled as an explicit `ApiTransportTimeoutError` rather than a fabricated result. That is good failure behavior.
  - Impact: threadpool worker is held for the full run duration, and a re-submit or burst (aggravated by no auth/rate limit above) can stack runs. Recommend documenting that a timed-out run continues server-side and is inspected via GET.

### Minor
- `backend/persistence/database.py:62-68` — `session_scope` yields a session and closes it without an explicit `commit()` or `rollback()`. Read-only routes are fine, and mutation routes correctly wrap with `with db.begin()` (e.g. `experiments.py:220`, lifecycle transactions). This is a footgun: any future mutation path that uses `session_scope` without an explicit transaction will silently discard writes on close. Consider committing on clean exit (or naming the helper to make the no-transaction contract obvious).

- `frontend/next.config.ts:3-8` — `ATLAS_API_BASE_URL` is read at build time and is **not** loaded from the repo-root `.env` (Next.js loads `.env` from the `frontend/` project directory; there is no `frontend/.env`, confirmed via `ls`). It must be shell-exported for dev and build. The fail-fast `throw` when missing is good, but the root `.env` placement vs. `frontend/` env loading is a setup mismatch worth documenting.

- `backend/api/experiments.py:77-94` — `_json` recurses into `vars(value)` (`__dict__`) for any object lacking a SQLAlchemy mapper, skipping only underscore-prefixed keys. Bounded to read-service dataclasses today, but a broad serialization seam: if a future value type carries non-underscore internal fields, they will leak into API responses. Prefer explicit field allowlists for response shaping.

- `backend/experiments/lifecycle.py:74-80` — `_APPROVED_EXCEPTION_CLASSES` allowlist is good, but note `_exception_class` maps anything else to `"UNCLASSIFIED_EXCEPTION"`; the hostile-detail tests (`test_runner_diagnostics.py:48-65`) confirm no raw detail is emitted. This is working as intended; retained as an observation, not a defect.

---

## 3. Performance Findings

- **No material performance defects found** within scope. Pagination is present (`cursor` on listing, `limit` bounds `le=100`/`le=250`), DB queries are targeted, and strategy evaluation is pure/deterministic. The only throughput concern is the synchronous long-running `run` endpoint noted in Best-Practices (Important), which compounds only with unauthenticated access.

---

## 4. Verification results by requested scope

- **local-first**: Confirmed intentional. DB + API + runtime run on loopback/local PostgreSQL; no cloud services. `README.md:7-12, 79-99`. Good fit for the single-user design.
- **DB**: Strong integrity enforcement. `models.py:53-192` uses `CheckConstraint` (positive version, EUR/USD-only, M1-only, minute-aligned, completed-only, positive/finite OHLC, OHLC containment, sha256 fingerprint regex, valid integrity_summary) plus `UniqueConstraint` and partial unique indexes. `session_scope` transaction footgun (Minor) noted above.
- **API**: Unauthenticated, no CORS/rate-limit/TrustedHost (Important); synchronous run (Important); `/docs` enabled (Minor).
- **runtime**: Minimal and correct — signal handling (`SIGINT`/`SIGTERM`), readiness check, clean dispose. `runtime/main.py:35-39`. No supervisor/bot abstractions, matching architecture guidance.
- **secrets**: Clean. `.env` is gitignored (`git check-ignore` confirms) and untracked (`git ls-files` shows only `.env.example`); no `.env` in git history; OANDA token is `SecretStr` (`config.py:32`), sent only as an Authorization header to the fixed HTTPS Practice endpoint (`source.py:269-270`), never a CLI arg/output, and `hide_input_in_errors=True` (`config.py:25`) prevents validation-error leakage. No real token found in tracked files.
- **Strategy**: Boundary respected. `contract.py` enforces immutable definition, EUR/USD M15 MID only, warm-up bar minimum, and the no-lookahead / same-completed-bar-never-evaluated-twice invariant via the frontier check that raises `DuplicateBarEvaluationError` (`contract.py:189-194, 220-227`). Strategy has no broker/DB/UI access.
- **lifecycle**: Durable and safe. Durable `RUNNING` claim before facts (`lifecycle.py:239-242`), row-lock dedup, atomic commit, fallback failure persistence, and sanitized error classes (`_exception_class` allowlist) with hostile-detail tests. Positive.
- **shipping / core-shell**: Build gates exist (`check:web` = format + lint + typecheck + test + build; `ATLAS_API_BASE_URL` fail-fast). The main gap is the lack of any auth/rate-limit/origin trust around the API + Next proxy (Security, Important) and the sync-run/8s-timeout behavior (Best-Practices, Important).

---

## 5. Counts

| Category | Critical | Important | Minor |
|----------|----------|-----------|-------|
| Security | 0 | 1 | 1 |
| Performance | 0 | 0 | 0 |
| Best Practices | 0 | 1 | 4 |
| **Total** | **0** | **2** | **5** |

## 6. Top priorities
1. **API trust boundary** (Security/Important) — no auth, no rate limit, no origin/trusted-host restriction, proxied by the Next server that binds `0.0.0.0` in `next start`. Confirm loopback-only binding in the actual deployment and consider a reverse-proxy/auth layer before any network exposure; it is the only current blocking architectural risk.
2. **Synchronous long-running `run` vs. 8s client timeout** (Best-Practices/Important) — behavior is safe but must be documented/validated as intended for the PAPER/LIVE path.

## 7. Limitations
- Assessment is static/code-level; I did **not** run the credentialed OANDA `external` test or stand up the full stack (read-only audit). Those remain `Needs manual review` for live behavior.
- The eventual PAPER/LIVE auth and exposure model cannot be assessed because no auth exists yet; this is noted as the top gap rather than a defect of the current local-only slice.
- The `.env` on disk contains a real-length OANDA token (redacted here); it is untracked/gitignored, but ensure it is excluded from any backup, sync, or CI export.

The developer owns all fix decisions.
