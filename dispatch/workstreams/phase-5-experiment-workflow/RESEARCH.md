# Phase 5 E2E failure diagnosis

## Scope and evidence basis

Read-only diagnosis of the five failures recorded in `TASK-10.md`; no browser or
commands were run during this investigation. The recorded rerun is the primary
runtime evidence (`TASK-10.md:118-131`). Source facts below are cited by path and
line range.

## Findings

### 1. `Validate coverage` is disabled in valid, invalid, and zero-Trade cases

**Classification:** E2E harness/config (common upstream failure), with a possible
frontend/API transport symptom. **Product vs test judgment:** not a coverage
fixture defect; the three scenarios share the same missing configuration state.
**Phase 5 acceptance:** **blocks** acceptance because configure/validate and the
valid/zero-Trade paths are not browser-covered.

**Fixture state (fact).** `global-setup.ts` invokes `backend.tests.e2e_seed` and
writes the IDs to `tests/e2e/.fixtures.json` (`tests/e2e/global-setup.ts:4-10`,
`backend/tests/e2e_seed.py:19-56`). The seed creates an OANDA/EUR_USD,
phase-4-shaped snapshot with coverage ending at `START + 1590 minutes`, a
runnable EMA version with 100 warm-up bars, and one intentionally invalid-config
Experiment (`backend/tests/e2e_seed.py:46-55`; the underlying fixture is
`backend/tests/integration/test_golden_flows.py:160-213`). The valid test requests
2026-01-06 01:00–01:30, the invalid test extends to 02:00, and the zero-Trade
test requests 01:00–01:15 (`tests/e2e/experiment-workflow.spec.ts:8-19,46-55,69-77`).
The recorded result therefore does not implicate the failed-Experiment fixture
or the period values. **Confidence: high.**

**API response/state transition (fact plus bounded inference).** On page mount,
`ExperimentForm` requests `GET /api/v1/experiments/configuration-options`; only
after that response does it set `strategy` and `snapshot`
(`frontend/components/experiment-workflow.tsx:629-645`). The coverage button is
disabled whenever either ID or either date is absent
(`frontend/components/experiment-workflow.tsx:965-978`), while the test fills
only the dates (`tests/e2e/experiment-workflow.spec.ts:12-15`). The API route
does return `strategyVersions` and `datasetSnapshots` in the expected camel-case
shape (`backend/api/experiments.py:183-200`), and the client calls the expected
path through `/atlas-api` (`frontend/lib/api-client.ts:63-70`). The recorded
rerun explicitly says configuration options did not load and controls stayed
disabled because Next development resources were blocked cross-origin
(`TASK-10.md:95-99`); after the origin repair it still reports all three
validation clicks timing out on the disabled control (`TASK-10.md:118-128`).
Thus the rendered disabled state is explained by `strategy`/`snapshot` remaining
empty; the exact post-repair HTTP response is not captured. **Confidence: high
for the state transition; medium for the still-unresolved transport cause.**

**Rendered DOM / expectation.** The test clicks `Validate coverage` before it can
ever issue `POST /coverage-validations`; it consequently never reaches either
`The selected period is eligible to run.` or `This period cannot run yet.`
(`tests/e2e/experiment-workflow.spec.ts:15-19,46-55`). This is a shared
configuration-load/harness failure, not three independent backend coverage
failures.

**Smallest safe remediation.** Reproduce the browser request/console response
and align the dev origin used by Playwright with Next's development-origin
allow-list, keeping the same origin consistently in `playwright.config.ts:6-25`
and `frontend/next.config.ts:13-19`; the already-applied origin change is the
likely repair location, not the coverage service or seed. If the request is
shown to succeed, then the smallest frontend repair is in
`frontend/components/experiment-workflow.tsx:629-645` (surface the options-load
failure and/or ensure defaults are applied only from a successful response), but
that is a secondary inference and should not be made without the response.

### 2. Failed Experiment lacks expected persistent text

**Classification:** stale expectation. **Product vs test judgment:** the product
behavior is present; the E2E selector uses different copy from the implemented
and component-tested copy. **Phase 5 acceptance:** **does not independently
block** product acceptance, but the failed-state E2E gate remains red until
expectation/copy is aligned.

**Fixture/API/state (facts).** The seed returns `failedExperimentId` for the
intentionally invalid Phase 4 simulation config (`backend/tests/e2e_seed.py:46-55`;
`backend/tests/integration/test_golden_flows.py:200-212`). The runner catches the
invalid config and persists a terminal failed state with no result
(`backend/experiments/runner.py:251-269,340-348`; the no-result regression is
`backend/tests/integration/test_golden_flows.py:349-359`). The run route first
checks existence, runs synchronously, then reads the durable detail
(`backend/api/experiments.py:282-290`), whose failure payload is
`category/code/detail` (`backend/api/experiments.py:97-121`). **Confidence: high.**

**Frontend transition/DOM (facts).** The detail page loads the failed fixture,
clicks `Run Experiment`, polls/reads `FAILED`, and renders the persistent
fail-closed panel. Its exact heading text is `No trustworthy full result was
created.` (`frontend/components/experiment-workflow.tsx:1130-1144`), followed by
failure detail and next action; completed-only result content is gated behind
`status === 'COMPLETED'` (`:1146-1149`). The E2E expects the substring
`No trustworthy full result exists` (`tests/e2e/experiment-workflow.spec.ts:60-67`),
which is absent. Frontend regression tests assert the implemented “was created”
copy (`frontend/tests/experiment_results.test.tsx:150`). The recorded rerun
confirms the page reaches this point but cannot find the E2E text
(`TASK-10.md:124-129`). **Confidence: high.**

**Smallest safe remediation.** Align the selector in
`tests/e2e/experiment-workflow.spec.ts:64` with the existing persistent copy
(or, only if product copy is explicitly chosen, change the component and its
frontend test together). No backend change is indicated.

### 3. Foundation is missing an `Atlas` heading

**Classification:** stale expectation. **Product vs test judgment:** the Atlas
brand is rendered as a link, not a heading; the approved shell does not require
the brand to be an `h1`. **Phase 5 acceptance:** **does not independently block**
the Experiment workflow; it blocks the current full E2E suite until the
foundation expectation is corrected.

**Fixture/API/frontend state (facts).** `/` redirects to `/experiments`
(`frontend/app/page.tsx:1-5`). The shell renders the brand as
`<Link>Atlas</Link>` (`frontend/components/app-shell.tsx:21-32`) and the page's
actual heading is `Experiments` (`frontend/components/experiment-workflow.tsx:478-493`).
The title expectation was already repaired to `Atlas · Experiments`, and the
rerun confirms that title now passes but the heading assertion fails
(`TASK-10.md:106-123`). **Confidence: high.**

**Smallest safe remediation.** Change only
`tests/e2e/foundation.spec.ts:5` to assert the visible Atlas link (or the
`Experiments` heading), preserving the current shell. Adding a heading to
application markup would be unnecessary product/UI change unless a separate
accessibility/product requirement is approved.

## Overall acceptance judgment

The disabled validation controls are the only finding that blocks meaningful
Phase 5 workflow acceptance: they prevent the browser from proving configure →
validate → create/run, including valid and zero-Trade paths. The failed-state
copy and foundation heading are selector/expectation alignment issues, not
evidence of backend financial or result-state defects. No Phase 6 behavior was
investigated.

## 2026-08-23 — Approved read-only valid-run investigation

### Conclusion and classification

**Classification: Phase 5 create/orchestration defect (unproven exact trigger;
medium confidence).** The durable `MARKET_DATA / INVALID_INPUT` is produced by
the existing Phase 4 execution path after Phase 5 creates the Experiment. The
available receipts do not preserve the original exception text, so it is not
responsible to name a more specific data assertion as the exact trigger. It is
also not supportable to classify this as a fixture defect, current-time/session
dependency, or Phase 4 regression: the same Phase-4-shaped seed and range pass
the known-good Phase 4 golden test.

### End-to-end trace

* **Seed and identity:** `backend/tests/e2e_seed.py:21-55` imports the Phase 4
  golden `START`/`_seed`, seeds OANDA `EUR_USD`, the archived
  `ema_sweep_engulfing.v1` StrategyVersion, and the primary snapshot; it writes
  IDs for the browser at `:96-105`. The zero snapshot is bounded at
  `START + 1515 minutes` and maps every source bar with `start_time < zero_end`
  (`:58-95`).
* **Coverage and persisted inputs:** coverage computes 100 warm-up M15 bars,
  derives the required start, and validates the snapshot members at
  `backend/experiments/configuration.py:242-295`; creation re-runs that check
  and persists the requested times and Phase 4 model/config at `:312-364`.
  The browser sends UTC ISO values (`frontend/components/experiment-workflow.tsx:656-667,681-704`).
  The primary E2E range is `2026-01-06 01:00`–`02:30` and the zero-Trade range
  is `01:00`–`01:15` (`tests/e2e/experiment-workflow.spec.ts:12-15,66-74,137-160`).
* **Repository boundary:** the runner loads the persisted snapshot by
  fingerprint, then reads only immutable snapshot membership over descriptor
  coverage (`backend/experiments/runner.py:194-202`; the repository explicitly
  omits `is_current` at `backend/persistence/market_data_repository.py:515-520`)
  and filters MID for aggregation. It does not query OANDA or mutable current
  bars.
* **M1 completeness/session policy:** aggregation rejects missing constituents
  rather than filling (`backend/market_data/aggregation.py:62-76`). Runtime
  observations require exactly ASK/BID/MID and reject incomplete open minutes
  (`backend/experiments/clock.py:189-216`). Scheduled closures are skipped by
  the versioned New York policy (`backend/market_data/session_calendar.py:28-50`);
  the seed uses that same predicate (`backend/tests/integration/test_golden_flows.py:126-147`).
* **Warm-up/decision path:** `SimulationClock` selects the last 100 completed
  M15 bars ending no later than trading start and rejects insufficient warm-up
  (`backend/experiments/clock.py:110-119`); frames distinguish warm-up from
  decision frontiers and do not reuse the signal interval (`:218-268`). The
  Phase 4 runner invokes observations, frames, strategy, risk, execution, and
  finalization at `backend/experiments/runner.py:275-339`.
* **Exact recorded failure boundary:** both E2E runs reached durable `FAILED`
  with `MARKET_DATA/INVALID_INPUT` (`dispatch/workstreams/phase-5-experiment-workflow/TASK-11.md:40-46,60-63`).
  The only code that emits that exact category/code for a Phase 4 run is the
  broad `ValueError` handler at `backend/experiments/runner.py:340-348`; it
  sanitizes the detail to `Experiment could not be run`. Therefore the
  evidence establishes the raise *class and handler*, but not which underlying
  ValueError occurred.

### Comparison with known-good Phase 4

`backend/tests/integration/test_golden_flows.py:292-344` seeds the same
`phase4=True` 106-window dataset, uses the same `START + 1500` start and
`START + 1590` end, and passes the Phase 4 runner. Its configuration differs
  only in explicitly supplied simulation details such as commission, while the
  Phase 5 service generates the same required schema (`backend/experiments/configuration.py:38-69`).
  The Phase 4 test also proves deterministic replay and persistence. Existing
  Phase 4 regressions therefore cover the expected non-zero behavior, but no
  existing regression covers the complete Phase 5 UI-create → Phase 4-run path
  or a zero-Trade run through `_complete_phase4`.

### Zero-Trade semantics and time independence

A valid zero-Trade period must complete with equity history and a result whose
trade count is zero; trade-dependent metrics are explicitly unavailable or
zero-trade classified (`backend/experiments/metrics.py:114-144`,
`backend/tests/experiments/test_metrics.py:112-125`). The feature contract
explicitly says zero-Trade is valid (`context/features/experiments.md:71-73`).
Nothing in the inspected fixture, coverage, repository, aggregation, clock, or
runner input uses wall-clock time, current market session, live OANDA, or the
current Forex-open state. The runner uses `datetime.now(UTC)` only for durable
completion/failure timestamps (`backend/experiments/runner.py:529-530,590-597`),
not market-data selection. Session classification is purely timestamp-based.

### Remediation boundary

Smallest corrective scope is to capture the unsanitized underlying ValueError
at the E2E/API boundary (without exposing secrets), then add one narrow backend
regression that creates through `ExperimentConfigurationService` and runs both
the primary and zero-Trade persisted configurations. Correct the first failing
contract at the create/orchestration boundary only; do not change Phase 4
semantics, session policy, or historical data access absent that receipt. No
exact application file can be named beyond the likely orchestration/fixture
surface (`backend/experiments/configuration.py`, `backend/experiments/runner.py`,
or `backend/tests/e2e_seed.py`) because the current receipt discards the cause.
Confidence is high that the failure is deterministic and historical, high that
it is not OANDA/current-time dependent, and medium/low on the underlying raise
site. Investigation stopped at this recommended remediation scope; no code,
 test, fixture, database, Git, or Phase 6 changes were made.

## 2026-08-23 — Approved read-only E2E persistence-failure investigation

### Conclusion and root-cause classification

**Classification: exact database exception unproven; probable lifecycle transaction/connection
failure, not a demonstrated Phase 5 domain-input failure (low-to-medium confidence).** The
only durable fact available after Task 13 is that the outer lifecycle exception path was
entered and the fresh fallback transaction persisted `PERSISTENCE/PERSISTENCE_FAILURE`.
The stored/API detail intentionally discards the exception. No inspected artifact contains
the server traceback, SQLSTATE, or failing statement, so naming a particular PostgreSQL
operation as proven would be speculation.

The strongest bounded conclusion is that the failure is after the E2E request reaches
`ExperimentRunService.run`, or during its transaction commit/close, rather than a normal
runner `ValueError`: normal runner domain failures are converted to a terminal result and
committed, while the outer `except Exception` invokes the new-session fallback
(`backend/experiments/lifecycle.py:46-69`). The fallback's `mark_failed` operation is the
durable operation responsible for the observed invariant, but it is a recovery operation,
not evidence of the original failure.

### Request and persistence trace

* Playwright submits the browser command to `/atlas-api/api/v1/experiments/{id}/run`
  (`tests/e2e/experiment-workflow.spec.ts:77-100,137-160`). The frontend client uses the
  same prefix and POST (`frontend/lib/api-client.ts:71-79`).
* Next rewrites `/atlas-api/:path*` to the configured FastAPI base URL, stripping the
  prefix (`frontend/next.config.ts:19-25`). Playwright starts FastAPI on `127.0.0.1:8000`
  with `ATLAS_DATABASE_URL` set from `ATLAS_E2E_DATABASE_URL`, and starts Next with the
  same API target (`playwright.config.ts:6-21`).
* FastAPI creates one engine/session factory and one lifecycle service at app composition
  (`backend/api/app.py:23-52`). The route first reads the Experiment, calls the lifecycle,
  then opens a fresh read session for the response (`backend/api/experiments.py:282-290`).
  The dependency session used by the initial existence check is not passed into the run.
* Lifecycle first claims `PENDING` as `RUNNING` in one transaction and commits that claim;
  it then opens a second session/transaction, locks the row, runs the existing runner, and
  commits the terminal graph (`backend/experiments/lifecycle.py:46-64`,
  `backend/persistence/experiment_repository.py:199-209`). Any exception outside the
  runner's returned domain failure enters the fallback (`lifecycle.py:65-69`).
* The fallback obtains a third, fresh session, locks the still non-terminal row, and calls
  `mark_failed`, which flushes `FAILED`, category `PERSISTENCE`, code
  `PERSISTENCE_FAILURE`, and the sanitized detail (`backend/experiments/lifecycle.py:102-122`,
  `backend/persistence/experiment_repository.py:161-197`). The model requires terminal
  status and non-null completion/failure fields (`backend/persistence/models.py:227-258`).

### UTC policy and path comparison

The intended policy is present on the inspected API and seed paths. The application engine
is configured by `create_database_engine`, and the session factory repeats the idempotent
registration (`backend/persistence/database.py:25-49`). Both `connect` and pooled
`checkout` execute `SET SESSION TIME ZONE 'UTC'` with temporary DBAPI autocommit
(`database.py:10-35`). The E2E seed explicitly applies the helper before seeding
(`backend/tests/e2e_seed.py:27-40`), and migration composition applies it before connecting
(`backend/persistence/migrations/env.py:28-45`). Thus server/database/role defaults and
the host `TZ=America/Los_Angeles` should not select the PostgreSQL session timezone.

The direct Phase 5 regression uses the same helper and real service/runner path
(`backend/tests/integration/test_phase5_valid_run.py:96-205`) and passes for both the
primary and zero-Trade cases under the post-policy receipt (`TASK-13.md:74-83`). This is
not schema proof by itself, but the E2E seed upgrades to the same Alembic head and then
uses the same models (`backend/tests/e2e_seed.py:35-38`; `TASK-13.md:95-102`). No inspected
source shows an application-semantic ungoverned engine remaining, though
`backend/tests/integration/test_market_data_ingestion.py:57-71` uses a separately-created
factory and is not evidence about the E2E server.

There is no read-only evidence that the E2E API inherited a pre-policy pooled connection:
Playwright starts a fresh server with `reuseExistingServer: false` (`playwright.config.ts:9-11`),
and the seed disposes its engine (`backend/tests/e2e_seed.py:108-109`). A stale process or
connection remains a diagnostic unknown, not a supported explanation. Likewise, no schema
or migration divergence is shown: E2E runs `upgrade(head)` and direct tests target the same
database policy/migration composition. A live `SHOW TIME ZONE`, `pg_backend_pid()`, schema
revision, and connection checkout receipt from the failing server would be required to
prove those points; none is present in the safe artifacts.

### Runner, transaction, concurrency, and sanitization findings

The Phase 4 runner loads immutable snapshot membership, aggregates M1 to M15, constructs
the clock, runs the strategy/observation loop, closes any open position, creates the result,
and marks completion (`backend/experiments/runner.py:375-447,650-663`). Its broad final
handler converts unexpected runner exceptions to `PERSISTENCE_FAILURE` too
(`runner.py:448-457`), so the observed lifecycle fallback does not identify whether the
exception occurred during a flush, terminal `mark_completed`, transaction commit, or
another lifecycle boundary. The integration receipt proves the same candidate succeeds
with UTC policy, but does not prove E2E's original operation.

Polling is read-only and uses separate request sessions (`backend/api/experiments.py:179-181,
273-290`); it cannot itself mutate the run transaction. Duplicate commands are serialized
by the row lock and terminal retries are no-ops (`backend/experiments/lifecycle.py:54-64,71-100`).
The primary test's post-completion duplicate commands occur only after the UI observes
completion (`tests/e2e/experiment-workflow.spec.ts:90-100`), so they cannot explain the
initial failure. Two valid browser scenarios may run concurrently under Playwright's two
workers (`TASK-13.md:95-100`), but no receipt proves lock contention, deadlock, shared-runner
state, teardown, or a failed concurrent command. The runner does retain mutable execution
adapter state on the shared app runner (`backend/experiments/runner.py:265-275,369-374`),
which is a plausible concurrency diagnostic target, not a proven cause; both cases use the
same zero-slippage configuration.

Sanitization is operating as designed, not masking a recoverable domain result. The API and
durable fallback expose only the approved generic persistence message
(`backend/experiments/lifecycle.py:20-27,109-118`; `backend/api/experiments.py:97-100`),
and runner ValueErrors are separately mapped to the generic `MARKET_DATA/INVALID_INPUT`
message (`backend/experiments/runner.py:452-457`). This prevents identifying the original
exception, but changing it to expose raw detail would violate the failure/security contract
(`ARCHITECTURE.md:159-168,341-348`).

### Smallest safe scope and recommendation

Do not change the central UTC policy: it is explicitly required by architecture and is
installed on the intended API, migration, seed, connect, and checkout paths
(`context/architecture/database.md:31-35`; `backend/persistence/database.py:25-49`). Do not
change runner semantics, fallback sanitization, fixtures, migrations, or concurrency rules
on this evidence.

The smallest safe next diagnostic is one test-only, server-side, allow-listed diagnostic at
the lifecycle boundary that records only operation stage and exception class/SQLSTATE
(without message, SQL, credentials, paths, or traceback), plus `SHOW TIME ZONE`, backend
PID, and Alembic revision from the same failing API connection. It must distinguish runner
return, flush, outer transaction commit, fresh fallback lock/flush/commit, and final detail
read; it must be disabled in production and must not alter the fallback. If that diagnostic
proves a specific connection-policy defect, correct only the connection composition. If
it proves a shared-runner/concurrency defect, correct only ownership/lifecycle composition.
If it proves a schema constraint or SQL operation, compare the live revision/schema before
any application correction.

Regression extensions should then cover: API-process UTC on a fresh and pooled checkout;
primary and zero-Trade browser runs under non-UTC host `TZ`; concurrent primary/zero runs;
polling while the runner holds the lock; duplicate terminal commands; fallback persistence
after an injected commit/flush failure; and no leakage of diagnostic fields through API or
durable failure rows. These are recommendations only; no diagnostic was added here.

**Confidence:** high for the request/session/lifecycle trace, UTC policy inventory,
sanitization behavior, and the direct-vs-E2E result distinction; medium that the original
failure is a transaction/connection or shared-concurrency issue; low for the exact DB
statement/constraint because the required exception evidence is absent.

**Unknowns:** exact SQLSTATE/operation, whether the E2E server actually reported UTC on
every checkout, live schema revision at failure, stale external processes/connections,
whether two workers overlapped the runner, and whether teardown interrupted a request.

**Stop-after-recommendation:** this investigation stops here. No corrective change is
authorized or recommended until the smallest safe diagnostic identifies the original
operation and invariant failure.
