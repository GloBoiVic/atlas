# PLAN - UI 01 Trader Shell and Read-Only Overview

## Workstream state

- **Workstream:** `ui-01-trader-shell-read-only-overview`
- **Classification:** `Feature`
- **Base:** `main` at `459e4a298c80b87b28b2875069fd49795ddef478`
- **Branch:** `solo/ui-01-trader-shell-read-only-overview`
- **Phase:** `READY_FOR_USER`
- **Approval:** Developer approved implementation on 2026-09-08
- **Architecture:** Not required; this is a frontend composition slice over existing contracts
- **Task state:** T001, T002, and T003 `DONE_WITH_CONCERNS`; R001 BUILD and VALIDATE `DONE_WITH_CONCERNS`/`PASS`
- **Next action:** Await explicit merge approval; GIT END is not authorized
- **Worktree concern:** Pre-existing untracked `.DS_Store` files are not part of this workstream

## Outcome

Make Atlas a trustworthy trader-facing shell for the current lifecycle:

```text
Strategy -> Experiment -> PAPER -> LIVE
```

The home route becomes an Overview. Strategies and Experiments remain the existing
product workflows. PAPER and Data gain read-only visibility over facts already exposed
by the API. LIVE and Journal remain unavailable or deferred. This workstream does not
add trading controls, new broker truth, persistence, or backend behavior.

## Current-state findings

- `frontend/app/page.tsx` redirects `/` to `/experiments`; there is no Overview route.
- `frontend/components/app-shell.tsx` still presents `Dashboard` and `Deployments` as disabled, marks Data as disabled, and says `PAPER and LIVE are future-only`.
- `frontend/components/api-status.tsx` labels a successful `/health/ready` response as `PAPER · connected`, which overstates what the health contract proves.
- `/strategies` and `/experiments` already provide useful catalog, immutable StrategyVersion, setup, run, result, and Trade inspection workflows and should not be rebuilt.
- The existing dark-first Atlas tokens, shell, timezone selector, API retry status, loading patterns, and error panels are the visual and interaction baseline.
- The backend exposes safe PAPER GET routes for capability and active status. The active route returns `404 PAPER_ACTIVATION_NOT_ACTIVE` when no activation is active; this is the normal empty state and does not represent a historical activation.
- `PaperRuntimeStatusResponse` exposes activation identity/lifecycle facts, current financial position state, execution outcome, reconciliation status, and `terminal_runtime_state_does_not_prove_flat`.
- The backend also exposes historical-data capability and Experiment configuration options containing available DatasetSnapshots with coverage and fingerprint facts. There is no DatasetSnapshot history projection or PAPER activation history projection for this UI.
- `frontend/lib/api.generated.ts` currently contains the historical, Strategy, Experiment, and health paths but not the PAPER paths. The implementation may regenerate this frontend-only artifact from the current OpenAPI document before adding typed safe PAPER client methods; it must not hand-edit generated output or change the backend contract.

## Intended user experience

### Trader shell

- Make the Atlas wordmark link to `/`.
- Use current-level navigation links for `Overview`, `Strategies`, `Experiments`, `PAPER`, and `Data`.
- Remove stale `Dashboard` and `Deployments` entries.
- Keep `LIVE` visibly unavailable and non-interactive. Keep `Journal` out of the current workflow or visibly deferred rather than presenting it as available.
- Replace the future-only capability strip with concise lifecycle context: Strategies are authored and versioned, Experiments are deterministic historical research, PAPER status is observable but not controllable here, and LIVE is future.
- Preserve the API readiness indicator, display-timezone selector, keyboard focus behavior, and mobile horizontal navigation behavior.
- Change health copy to describe API readiness, not PAPER connectivity.

### Overview (`/`)

Render a real Atlas Overview with the message that Atlas is where the trader creates
methodologies, experiments with them, and operates approved methodology through PAPER.

The page will compose independent read-only status sections:

- **System readiness:** API readiness state and database check from `/health/ready`, with loading, unavailable, and retry states.
- **Strategy:** the number of Strategy catalog items returned by `/api/v1/strategies`, plus a link to the existing Strategies workflow. Do not call this a global total beyond what the response provides.
- **Experiments:** the visible first page from `/api/v1/experiments?limit=...`, with a clear visible/listed qualifier and status summary only from returned items. Do not fabricate a total or performance metric.
- **PAPER:** capability provider, environment, instrument, availability, and active status from the safe PAPER GET routes. A missing active activation is shown as an empty current-state result, not as a historical session result.
- **Data:** historical provider/instrument availability and available DatasetSnapshot count from existing GET contracts, with a link to Data.
- **Next steps:** links into existing Strategies, new Experiment, and Experiments workflows. These links do not submit mutations.

Each section must retain its own loading, empty, and API error state so one unavailable
read endpoint does not turn unrelated known facts into success or failure claims.

### PAPER (`/paper`)

Provide a lightweight read-only PAPER surface:

- Show capability facts from `GET /api/v1/paper/capability`, including provider, environment, instrument, supported availability, and a safe reason when unavailable.
- Request `GET /api/v1/paper/activations/active`; treat `PAPER_ACTIVATION_NOT_ACTIVE` as `No active PAPER activation reported`.
- If an active status exists, show only the status facts already exposed by that response, including lifecycle state, operational phase, current financial position state, execution outcome, reconciliation status, and the explicit terminal-runtime warning when the contract reports it.
- Do not request an activation detail unless the safe active response provides its activation ID.
- Explicitly state that the surface does not reconstruct historical activations or prove broker flatness. It must not imply that the stopped Dogfood 02 session is represented by `/activations/active`.
- Render no `ACTIVATE`, `STOP`, or reconcile control, no Buy/Sell or Close Trade action, no SL/TP editor, and no broker mutation affordance.
- Do not display provider credentials or invent account, Trade, P/L, RiskDecision, exit, realized-R, or reconciliation evidence that the current status contract does not provide.

### Data (`/data`)

Provide a small read-only historical-data view:

- Show historical capability provider, instrument, products, availability, and reason code from `GET /api/v1/historical-data/capability`.
- Show available DatasetSnapshots from `GET /api/v1/experiments/configuration-options`, using existing fingerprint, coverage start/end, schema, and integrity facts without adding a new projection.
- Optionally show the existing active historical load GET as current load status only; a missing active load is an intentional empty state.
- Show an explicit empty state when no snapshots are returned and a truthful unavailable/error state when the API cannot provide the data.
- Keep loading data and resuming loads inside the existing Experiment workflow; this page adds no load or resume mutation control.
- Format returned timestamps through the existing display-timezone preference.

## Existing API contracts to reuse

Only these read contracts are in scope for new UI reads:

| Contract | Use | Mutation allowed |
| --- | --- | --- |
| `GET /health/ready` | API/system readiness and database check | No |
| `GET /api/v1/strategies` | Strategy catalog summary | No |
| `GET /api/v1/experiments?limit=...` | Visible Experiment summary | No |
| `GET /api/v1/paper/capability` | PAPER provider/environment capability | No |
| `GET /api/v1/paper/activations/active` | Current active PAPER status | No |
| `GET /api/v1/paper/activations/{activation_id}` | Active status detail only when reached from a known active ID, if needed | No |
| `GET /api/v1/historical-data/capability` | Historical-data capability | No |
| `GET /api/v1/experiments/configuration-options` | Existing DatasetSnapshot options and coverage facts | No |
| `GET /api/v1/historical-data/load-requests/active` | Current historical load status, if used | No |

The client must not add or call `POST /api/v1/paper/activations`, the PAPER stop or
reconcile routes, or any broker mutation route. Existing Experiment POST/DELETE behavior
remains owned by the existing Experiment pages and is not expanded by this workstream.

## Frontend files and areas likely affected

Expected new areas:

- `frontend/app/paper/page.tsx`
- `frontend/app/data/page.tsx`
- `frontend/components/overview.tsx`
- `frontend/components/paper-status.tsx`
- `frontend/components/data-overview.tsx`

Expected shell/client updates:

- `frontend/app/page.tsx` to render Overview instead of redirecting.
- `frontend/app/layout.tsx` to use Atlas Overview metadata.
- `frontend/components/app-shell.tsx` to rationalize navigation and lifecycle copy.
- `frontend/components/api-status.tsx` to use accurate API readiness copy.
- `frontend/lib/api-client.ts` to add typed or narrowly validated safe GET methods and normal empty-state handling.
- `frontend/lib/api.generated.ts` only through current OpenAPI regeneration if required for the existing PAPER contract.

Expected focused test updates/additions:

- `frontend/tests/home_page.test.tsx`
- `frontend/tests/app_shell.test.tsx`
- `frontend/tests/api_status.test.tsx`
- `frontend/tests/api_client.test.ts` for safe PAPER/Data GET paths and empty/error semantics
- Focused Overview, PAPER, and Data component tests for loading, empty, unavailable, and populated states
- `tests/e2e/foundation.spec.ts` or a focused UI 01 smoke spec for `/`, `/paper`, and `/data`, including navigation and absence of PAPER mutation controls

Existing Strategy, Experiment setup, result, and Trade pages should receive only the
minimum shell integration required by the navigation change. No broad component rewrite
is planned.

## Frozen backend and safety boundary

UI 01 must not modify or require product changes in:

```text
backend/runtime/**
backend/paper/**
backend/risk/**
backend/integrations/oanda/**
backend/persistence/**
backend/strategies/**
backend/persistence/migrations/**
```

It also must not:

- run `atlas-runtime`;
- create or activate PAPER;
- call broker mutation endpoints;
- reconcile, restart, revive, or reuse Dogfood 02;
- alter OANDA Trade 11;
- change Candle Confirmation Break v1 or Risk policy;
- add migrations or a new backend API projection;
- change backend runtime, execution, persistence, activation, or reconciliation seams.

The only permitted contract-related change is regeneration or use of the frontend API
client artifact from the already existing backend OpenAPI contract. If that requires a
backend change, stop and surface the boundary crossing rather than widening UI 01.

## Deliberately deferred

Defer until Dogfood 02 closes and terminal reconciliation is understood:

- PAPER activation/session history or a frontend historical-session model;
- execution history, broker Trade/current exposure, entry/exit, SL/TP, P/L, RiskDecision detail, realized R, or terminal reconciliation evidence;
- any UI control that changes activation, runtime, broker orders, exposure, protection, or reconciliation;
- new backend projections, PAPER persistence, migrations, or richer account/execution contracts;
- LIVE operation or capability claims;
- Journal and broader product information architecture;
- expansion of historical market-data capability beyond existing GET responses.

## Validation plan

After approval and implementation:

- Run focused frontend tests covering Overview, shell navigation, API client safe GETs, PAPER empty/active/unavailable states, Data snapshot rendering, and timezone formatting.
- Run the focused Playwright smoke flow against the standard local API/frontend setup. Verify `/` is an Overview, current navigation links resolve, `/paper` and `/data` render truthful states, and no PAPER mutation controls or mutation requests are present.
- Use Safari Technology Preview for an independent browser check of loading, empty/error, responsive, keyboard-focus, and no-control behavior where available.
- Run `npm run check:web` as the frontend completion gate, including format, lint, typecheck, unit tests, and build.
- Inspect the final diff and verify that no frozen backend path, migration, credential, runtime command, broker mutation, or Dogfood 02 state was changed.

## Definition of done

1. `/` is a real responsive Atlas Overview and does not redirect to Experiments.
2. The shell presents Overview, Strategies, Experiments, PAPER, and Data as the current product surface, with LIVE clearly unavailable and Journal deferred or omitted.
3. Stale future-only PAPER messaging and the inaccurate `PAPER · connected` health label are removed.
4. Overview content is derived only from existing GET contracts and does not claim unsupported totals, broker state, or historical PAPER sessions.
5. `/paper` is read-only, handles capability and active-status empty/error states, and exposes none of the prohibited mutation controls or requests.
6. `/data` exposes only existing historical capability, DatasetSnapshot, and optional active-load facts without new data capability.
7. Existing Strategy and Experiment workflows remain usable and retain their timezone, loading, empty, error, and accessibility behavior.
8. Focused frontend tests and Playwright smoke coverage protect the lifecycle shell and PAPER safety boundary.
9. `npm run check:web` passes.
10. The implementation diff is frontend-only, contains no migrations, and preserves the frozen Dogfood 02/PAPER path.

## Approval gate

This plan was approved by the developer on 2026-09-08. GIT START was completed from
the recorded base `459e4a298c80b87b28b2875069fd49795ddef478` on branch
`solo/ui-01-trader-shell-read-only-overview`. BUILD tasks are now authorized.

Before approval, this plan prohibited:

```text
GIT START
create a solo/* branch
create tasks/T001
modify frontend application code
modify frontend tests
run implementation validation
```

After approval, the first READY BUILD task was created only after GIT START.
