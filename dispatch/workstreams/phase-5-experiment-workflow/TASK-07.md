# TASK-07 — Frontend foundation and generated client

- **Task:** Implement approved blueprint task 7 only.
- **Branch:** `feature/phase-5-experiment-workflow`
- **Scope:** Frontend foundation, same-origin API rewrite/config validation,
  generated OpenAPI TypeScript contract, typed client, shell, and persistent
  API availability state. No Experiment workflow pages were implemented.

## Changed files

- `frontend/app/experiments/page.tsx` — foundation-only Experiments landing
  surface; no list/config/detail/result/Trade workflow.
- `frontend/app/globals.css` — restrained light tokens, shell/status styles,
  focus-visible treatment, reduced-motion fallback.
- `frontend/app/layout.tsx` — metadata and provider host.
- `frontend/app/page.tsx` — root redirect to `/experiments`.
- `frontend/app/providers.tsx` — Sonner host.
- `frontend/components/api-status.tsx` — persistent API checking/connected/
  unavailable state.
- `frontend/components/app-shell.tsx` — horizontal Atlas navigation with
  future sections visibly disabled and Experiments active.
- `frontend/components/ui/button.tsx` — minimal approved shadcn-style button
  primitive for subsequent workflow tasks.
- `frontend/lib/api.generated.ts` — `openapi-typescript` generated OpenAPI
  contract artifact; API
  response bodies remain `unknown` where the FastAPI OpenAPI document currently
  exposes composition-owned JSON rather than a response model.
- `frontend/lib/api-client.ts` — typed same-origin fetch client over generated
  operation/request types; no handwritten semantic API models.
- `frontend/next.config.ts` — validated server-only `ATLAS_API_BASE_URL` and
  `/atlas-api/*` rewrite.
- `frontend/tests/api_status.test.tsx` — unavailable API persistent-state test.
- `frontend/tests/next_config.test.ts` — runtime rewrite mapping verification.
- `frontend/tests/home_page.test.tsx` — root redirect test.
- `package.json` / `package-lock.json` — approved `sonner`,
  `lightweight-charts`, `lucide-react`, and `openapi-typescript` dependencies.

## Outcome

Implemented the Phase 5 frontend foundation only. `/` now redirects to
`/experiments`; the shell is horizontal, desktop-first, restrained, keyboard
focusable, and does not render raw UUIDs or future feature pages. The browser
uses same-origin `/atlas-api/*` calls, while Next validates an absolute
HTTP(S) `ATLAS_API_BASE_URL` during config load/build and never exposes the
target to browser code. API failure remains a page-level status state rather
than a toast.

No Experiment list, configuration form, detail/results, chart, or Trade page
was added. Lightweight Charts is dependency-ready for task 9; no chart UI was
introduced. Sonner is mounted for transient feedback in later workflow tasks.

## R1 remediation — rewrite target and connected API state

Repaired the single Critical integration defect identified by R1 review. The
rewrite now maps `/atlas-api/:path*` directly to
`${ATLAS_API_BASE_URL}/:path*`, so `/atlas-api/health/ready` reaches
`/health/ready` and `/atlas-api/api/v1/experiments` reaches
`/api/v1/experiments` without an inserted or duplicated `/api` prefix.

Added runtime rewrite verification and a connected `ApiStatus` test. No Task 8
or Task 9 UI, unrelated cleanup, backend changes, or other dispatch artifacts
were touched.

## Exact validation receipts

- `npm run format:check:web` → **passed**; all files use Prettier style.
- `npm run lint:web` → **passed**.
- `npm run typecheck:web` → **passed** (`tsc --project frontend/tsconfig.json
--noEmit`).
- `npm run test:web` after R1 repair → **3 test files, 4 tests passed**; root
  redirect, persistent API-unavailable state, connected API state, and runtime
  rewrite verification covered. The connected state asserts the
  `/atlas-api/health/ready` client path.
- `next_config.test.ts` runtime rewrite test → **passed**; `next.config.ts`
  rewrites resolve to `http://localhost:8000/:path*` and explicitly reject the
  old `/api/:path*` destination.
- `npm run format:check:web` → **passed** after remediation.
- `npm run lint:web` → **passed** after remediation.
- `npm run typecheck:web` → **passed** after remediation.
- `ATLAS_API_BASE_URL=http://localhost:8000 npm run build:web` → **passed**;
  production build succeeds with the repaired destination.
- `git diff --check` → **passed** after remediation.
- `python -c "from backend.api.app import create_app; ..."` piped to a temporary
  OpenAPI document, then `npx openapi-typescript ... -o
frontend/lib/api.generated.ts` → **generated successfully** from the current
  FastAPI OpenAPI document.
- `ATLAS_API_BASE_URL=http://localhost:8000 npm run build:web` → **passed**;
  production build compiled, typechecked, and generated `/` and `/experiments`.
- `ATLAS_API_BASE_URL=not-a-url npm run build:web` → **failed fast as intended**
  with `ATLAS_API_BASE_URL must be set to an absolute http(s) URL...`.
- `git diff --check` → **passed**.
- UUID-label scan over `frontend/**/*.{ts,tsx,css}` → **no matches**.
- Keyboard/focus/contrast review → semantic links/buttons, visible
  `focus-visible` rings, non-color status labels/icons, and readable dark text
  on light surfaces are present in the shell. No browser automation or visual
  contrast tool was available in this validation pass.

## Blockers / conflicts

None. The OpenAPI response schemas for the current FastAPI routes are
composition-owned untyped JSON (`additionalProperties: true`/empty schema), so
the generated artifact correctly does not invent frontend response models.
Tasks 8–9 must consume/extend the backend-owned response schemas if stronger
generated response types are required; this task does not duplicate them.

No Git mutations were performed. Pre-existing backend and dispatch changes were
left untouched.
