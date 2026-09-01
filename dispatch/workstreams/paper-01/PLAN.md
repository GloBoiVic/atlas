# PAPER 01 — Bounded OANDA Practice Vertical Slice

## Outcome

Define the smallest trustworthy architecture and implementation boundary for one
explicit OANDA Practice account and EUR/USD Deployment to prove:

`StrategyVersion → Strategy evaluation → TradeIntent → PRE_FLIGHT RiskDecision →
PRE_SUBMISSION RiskDecision → OANDA Order → authoritative OANDA Fill → Position →
Trade → broker reconciliation`.

The slice reuses the existing immutable `EMA Sweep Confirmation Break v2`
StrategyVersion and methodology. It changes neither the meaning of existing
Experiments nor the Strategy boundary. This workstream is planning and
architecture only; it does not build or activate PAPER.

## Classification and authority

- **Classification:** `Critical`.
- **Baseline:** `main` at `e671190ae4a77282367f2cecfa27ef45a375add1`.
- **Branch:** `solo/paper-01` (GIT START completed from `main`).
- **Base SHA:** `e671190ae4a77282367f2cecfa27ef45a375add1`.
- **Foundation:** Freeze 07 closed.
- **Requirements source:** `dispatch/workstreams/pre-paper-audit/AUDIT.md`.
- **Audit verdict:** `READY FOR PAPER 01` means ready to plan/implement, not
  authorized to activate, submit orders, or change credentials/Risk policy.
- **Current phase:** `REVIEW — FAILED; stop`; developer approved reopening C004
  only for V-C004-01a. Fresh PostgreSQL-backed targeted validation is `PASS`
  with all 86 checks passing and no skips, and V-C004-01a passed rereview. The
  independent rereview found new CRITICAL V-C004-02 (reconciler can forge
  `durable_gate_proven=True`) and V-C004-03 (Account Changes Order cancel/reject
  facts can advance the cursor without applying the canonical Order projection),
  plus IMPORTANT V-C004-04 (UNKNOWN full-fill recovery incomplete). Per the
  explicit instruction, stop without automatically requesting remediation.
  C001-C003 remain closed. C005/F-07/F-09 remain untouched and unauthorized.
- **Git:** `GIT START` is authorized by the developer request and must start from
  `main` at the recorded baseline. No commit, merge, push, activation, or
  capital-capable OANDA request is authorized.
- **Tasks:** T001–T004 are bounded BUILD tasks created from the frozen PLAN and
  ARCHITECTURE. Tasks are sequential because later seams depend on earlier
  contracts and persistence.

If audit findings and source disagree, the contradiction must be recorded in the
architecture and surfaced for developer resolution. No frozen Experiment,
Strategy, Risk, accounting, broker-authority, or market-data meaning may be
silently changed.

## Scope

### In scope for PAPER 01

1. OANDA Practice only, one explicitly selected Practice account, USD base,
   EUR/USD only, one Deployment, one Position maximum, and one pending opening
   setup maximum.
2. Existing EMA Sweep Confirmation Break v2 with immutable methodology/config
   identity, native completed M15 MID analysis, and executable BID/ASK entry
   observations strictly after the decision frontier. Equality at the frontier
   is ineligible. Entry eligibility preserves the Experiment predicate exactly:
   LONG `ASK open > trigger OR ASK high >= trigger`; SHORT `BID open < trigger
   OR BID low <= trigger`.
3. Explicit trader START approval, durable desired/actual Deployment state,
   single runtime ownership, and loopback/local Atlas authority.
4. Durable Strategy state envelope, last completed-M15 evaluation frontier,
   pending-entry handoff, restoration validation, and duplicate-evaluation
   prevention.
5. Normalized broker account, instrument, pricing, tradeability, margin,
   precision, and session/trading-hours facts outside Strategy.
6. Mandatory centralized Risk composition: PRE_FLIGHT followed immediately by
   PRE_SUBMISSION, conservative provider-valid quantity, account/exposure/margin
   checks, and a priceBound or equivalent worst-executable-price constraint.
7. Canonical OANDA-backed MARKET/FOK entry Orders only. IOC is unsupported.
   Stable Atlas correlation plus external OANDA Order/Trade/Fill/Transaction
   identities and durable transaction cursor.
8. Full-fill-only PAPER 01 behavior: unexpected partial fill/state is a
   fail-closed condition; general partial-fill support is PAPER 02.
9. Broker-hosted stop protection immediately on entry where OANDA supports it;
   target derived from the authoritative actual Fill at 1.7R, then attached and
   confirmed. Missing or ambiguous protection blocks/fails closed.
10. Startup, reconnect, and uncertain-submission reconciliation before actual
    RUNNING, with broker authority, durable safety state, and no blind retry.
11. Minimum persistence extensions that preserve immutable historical facts and
    use canonical `TradeIntent`, `RiskDecision`, `Order`, `Fill`, `Position`,
    and `Trade` nouns.
12. Non-capital validation design: deterministic unit/contract tests, mocked or
    recorded provider-shape tests, migration checks, and safety/reconciliation
    scenarios. Credential-dependent and capital-capable validation remain behind
    a later explicit approval boundary.

### Reconciled developer hold decisions

The following five decisions are now frozen requirements for ARCHITECTURE.md and
any later implementation; they do not broaden the approved slice:

1. **Execution eligibility:** an M1 observation is eligible only when
   `observation.start_time > decision_time`; equality is ineligible. The exact
   Experiment trigger predicate is reused: LONG is
   `ASK open > trigger OR ASK high >= trigger`, and SHORT is
   `BID open < trigger OR BID low <= trigger`. Do not replace this with a
   current-tick or arbitrary-price predicate.
2. **PAPER RiskDecision target:** `PRE_SUBMISSION.target_price` is `NULL` / not
   final for PAPER. It persists the approved stop and immutable Strategy target
   methodology/multiple plus quote/executable evidence, but never a quote-derived
   final target. The final 1.7R target is created only after the authoritative
   Fill; existing Experiment target behavior remains unchanged.
3. **Canonical ownership:** each canonical root fact has one unambiguous owner.
   TradeIntent, Order, Position, and Trade are directly owned by exactly one
   Experiment or Deployment; RiskDecision is owned transitively by its
   TradeIntent; Fill is owned transitively by its Order. Cross-links must resolve
   to the same root owner. No PAPER row receives a fabricated Experiment ID.
   `StrategyStateEnvelope.pending_entry` remains the sole methodology authority
   for trigger/frontier/watch-count state. Any runtime pending-entry row is only
   an intent/lifecycle link and status, never a second source of that truth.
4. **Runtime ownership:** one session-level PostgreSQL advisory lock keyed by
   Deployment is the concrete PAPER 01 ownership primitive. Durable heartbeat
   and health facts accompany it. Lost DB connectivity or lock ownership blocks
   new exposure; reacquisition always requires reconciliation before RUNNING.
5. **MT4 capability:** PAPER 01 rejects MT4-associated OANDA Practice accounts
   at account validation/START because stable `clientExtensions` correlation is
   required for safe submission and recovery. No alternate correlation scheme is
   introduced.

### Out of scope

- Any build or application/test implementation in this phase.
- OANDA order/trade mutation, PAPER activation, LIVE, or second broker/account.
- Credential changes, Risk policy changes, multi-account/portfolio behavior,
  multi-instrument behavior, or generalized broker/runtime/plugin frameworks.
- IOC, limit-entry behavior, partial-fill/remaining-unit/reissue support,
  partial exits, pyramiding, trailing protection, or instant reversal.
- Strategy Studio, UI redesign, remote API/authentication work, distributed
  workers, queues, Redis, supervisors, or container-per-Deployment design.
- Reinterpretation of historical native M15/M1 semantics, Experiment meaning,
  StrategyVersion immutability, Fill authority, or broker authority.

## BUILD task state

| Task | State | Dependency | Scope |
| --- | --- | --- | --- |
| T001 | DONE | none | Pure PAPER contracts, OANDA read-only normalization, live data frontier and strict handoff eligibility |
| T002 | DONE | T001 | PostgreSQL TradingAccount/Deployment/state/handoff/safety facts, canonical ownership extensions, advisory lock, migrations and repositories |
| T003 | DONE | T002 | PAPER Risk composition, OANDA MARKET/FOK adapter, stable identities, full-fill-only response handling, protection and canonical Fill bridge |
| T004 | DONE | T003 | Narrow remediation of the three current review findings: compound provider Order identity agreement, immediate protected Trade exposure proof, and complete canonical Fill provenance; no F-07/F-09 or broader PAPER 01/PAPER 02 work |
| C001 | DONE | T004 | Analytical M15 validation/warm-up/frontier implementation complete; focused and isolated PostgreSQL C001 checks pass |
| C002 | DONE | C001 | Account binding, persisted PRE_SUBMISSION authority, and durable ENTRY idempotency implemented; focused and isolated PostgreSQL C002 checks pass |
| C003 | DONE | C002 | Restart continuity and durable health implementation complete; targeted isolated PostgreSQL C003 evidence passes (unrelated legacy broad migration assertion remains outside scope) |
| C004 | DONE (closure FAIL) | C003 | V-C004-01a remediation validated; independent rereview found new V-C004-02/V-C004-03 CRITICAL and V-C004-04 IMPORTANT findings; no automatic remediation or C005 |

C001-C004 are closure tasks, not reopenings of T004. They must execute
sequentially with fresh BUILD context. C005 may not begin until C001-C004 pass
targeted validation, the full non-capital backend suite, available isolated
PostgreSQL checks, and independent complete-capital-boundary review. No closure
task may activate PAPER, change credentials or Risk policy, invoke a mutating or
capital-capable OANDA request, or broaden into PAPER 02.

Task receipts remain in their canonical task files. No task may activate PAPER,
call a mutating OANDA endpoint, change credentials, or change Risk policy.

## Acceptance criteria for this planning phase

- `PLAN.md` and `ARCHITECTURE.md` exist under the canonical PAPER 01 workstream.
- Architecture freezes ownership, state machine, data/Risk/execution/protection/
  reconciliation flows, persistence, failure/UNKNOWN semantics, locks,
  idempotency/correlation, startup/restart/shutdown, and approval boundary.
- Every audit PAPER 01 disposition is addressed without broadening scope; every
  PAPER 02 and deferred item remains explicitly separated.
- Architecture explicitly proves Strategy remains pure and methodology-identical
  to Experiment; Risk remains external and authoritative; Fill alone changes
  exposure; broker truth wins in PAPER; no parallel Paper* nouns are introduced.
- Architecture defines explicit account selection and rejects inferred/first
  account selection; OANDA provider payloads stay behind a normalization seam.
- Architecture defines full-fill-only PAPER 01 handling and a fail-closed path for
  any partial/ambiguous result, without pretending PAPER 02 support exists.
- Architecture defines durable frontier/state/cursor/safety state and startup or
  reconnect reconciliation before actual RUNNING.
- Architecture freezes strict post-frontier eligibility and the exact existing
  Experiment LONG/SHORT trigger predicate, with no arbitrary tick substitution.
- Architecture freezes PAPER `PRE_SUBMISSION.target_price` as null/not-final and
  the authoritative-Fill-only 1.7R target transition.
- Architecture freezes exclusive direct/transitive Experiment-vs-Deployment
  ownership, database invariants, and the single methodology authority for
  pending-entry state.
- Architecture freezes a Deployment-keyed session-level PostgreSQL advisory lock,
  durable heartbeat/health, and reconciliation-required reacquisition.
- Architecture rejects MT4-associated Practice accounts because clientExtensions
  correlation is required; no fallback identity scheme is permitted.
- Architecture defines the first capital-capable action as separately gated after
  implementation, non-capital validation, and independent review; this phase
  performs no such action.
- Any audit/source contradiction is surfaced explicitly rather than resolved by
  silently changing a frozen contract.

## Validation strategy (planned; not run as activation)

The later implementation phase must validate, at minimum:

- Existing Experiment golden flows and Strategy conformance remain unchanged;
  same StrategyVersion/methodology receives equivalent canonical M15 inputs.
- Pure deterministic Strategy state transitions, warm-up, state serialization /
  restoration, invalid-state blocking, last-frontier duplicate prevention, and
  no-lookahead decision/execution separation.
- OANDA normalization for explicit account identity, USD/NAV/margin, EUR/USD
  instrument constraints, tradeability, BID/ASK quotes, FOK market response,
  external IDs, related transactions, and sanitized diagnostics.
- PRE_FLIGHT and PRE_SUBMISSION approval/rejection, account/exposure unknown,
  margin/precision/min-max constraints, conservative rounding, and priceBound.
- PENDING_SUBMISSION persistence, success/rejection/cancel mappings, timeout →
  UNKNOWN, no blind retry, authoritative Fill, and canonical Position/Trade
  transactionality. Any partial fill/state must fail closed in PAPER 01.
- Broker-hosted stop-at-entry, actual-Fill 1.7R target, target confirmation,
  missing/ambiguous protection, and preservation through shutdown/restart.
- Clean/repeated startup reconciliation, reconnect, unknown submission found or
  absent, pending Orders, open Trades/Position facts, transaction cursor replay,
  local/broker mismatch, manual drift, and broker-unavailable blocking.
- Persistence migration cycle, constraints, ownership lock, idempotency, and
  durable safety/health/frontier facts. Credential tests must be separate and no
  test may submit or mutate OANDA without the later explicit approval.

## Explicit finish line: `READY_TO_ACTIVATE`

PAPER 01 may be considered `READY_TO_ACTIVATE` only after a later approved BUILD
phase has implemented this architecture, non-capital validation and independent
review have passed with no unresolved Critical/Important findings, and the
selected Practice account, Deployment identity, immutable Strategy/Risk
configuration, session-policy provenance, broker connectivity, and safety gates
are visibly known. A separate explicit developer/trader approval is then required
for the first action capable of creating OANDA Practice exposure.

`READY_TO_ACTIVATE` does **not** mean activation has occurred. Before that
separate approval: no POST/PUT/PATCH/DELETE/cancel/close/transfer request, no
order submission, and no capital-capable runtime path may be invoked.

## PAPER 01 vs PAPER 02 boundary

### PAPER 01

Bounded single-account EUR/USD OANDA Practice slice; one Deployment/Position/
pending setup; explicit START; native completed M15 MID plus post-frontier
BID/ASK; durable Strategy state/frontier; two-stage Risk; FOK market entry;
full-fill-only with partial/ambiguous fail-closed; immediate broker-hosted stop;
actual-Fill target attach/confirm; stable identities and cursor; startup,
reconnect, and uncertain-submission reconciliation before RUNNING; local
loopback authority; pinned official OANDA session/trading-hours provenance before
activation.

### PAPER 02

General partial fills and remaining-unit/reissue handling across Order, Fill,
Position, Trade, and reconciliation; repeated polling/idempotency hardening;
manual drift/orphan-protection and broader recovery matrices; prolonged-downtime
stale/out-of-order/duplicate data recovery and chronological catch-up; any
provider/session-policy correction work not completed as a PAPER 01 gate;
operational safety/health hardening. PAPER 02 cannot weaken PAPER 01 fail-closed
behavior.

## Architecture reconciliation

The ARCHITECT-owned artifact is now frozen for developer review. It resolves the
plan as follows:

- One explicit OANDA Practice account ID is required; token authorization is not
  an account selector and the first authorized account is never inferred.
- The existing v2 StrategyVersion and Experiment composition remain untouched;
  live runtime composition supplies canonical completed M15 MID bars and
  post-frontier BID/ASK observations without Strategy I/O or environment logic.
- PAPER entry authorization is exactly PRE_FLIGHT then immediate PRE_SUBMISSION;
  only an approved PRE_SUBMISSION can create an Order. Quantity is conservative
  and provider-valid, and FOK plus a safe price bound prevents approved Risk from
  silently expanding through slippage.
- The canonical Order/Fill/Position/Trade path is reused. PAPER 01 accepts only
  an unambiguous full fill; partial/reissue/ambiguous outcomes fail closed rather
  than being represented as a false full position. General multiple-Fill support
  stays in PAPER 02.
- Stop-on-fill is required where advertised; the 1.7R target is calculated from
  the authoritative Fill and separately attached/confirmed. Protection remains
  broker-hosted through pause, shutdown, restart, and runtime loss.
- Startup, START, RESUME, reconnect, and uncertain submission all require
  reconciliation before actual RUNNING. Durable frontier/state, pending handoff,
  external IDs, transaction cursor, ownership, and safety state are required.
- The audit/source session-policy V1/V2 provenance discrepancy is surfaced, not
  silently resolved. Official current OANDA session/trading-hours provenance is
  an activation gate, while historical policy semantics remain versioned.

Canonical artifact: `dispatch/workstreams/paper-01/ARCHITECTURE.md`.

## Current phase / next action

- **Architecture status:** `FROZEN` and approved for this implementation phase.
- **Build task state:** T001–T004 `DONE`; C001-C003 `DONE`; C004 `DONE` pending
  independent rereview; C005 is not authorized.
- **Next action:** stop. Do not close C004, begin C005, activate PAPER, or
  request/dispatch remediation automatically. Any further C004 remediation for
  V-C004-02/V-C004-03/V-C004-04 requires new explicit developer approval.
- **Stop condition:** stop on any unresolved Critical/Important finding. Do not
  begin C005, claim `READY_TO_ACTIVATE`, activate PAPER, or invoke a
  capital-capable OANDA path.

## Implementation-closure analysis (hold)

This is analysis only; no application, test, fixture, schema, migration, or
dispatch implementation is authorized. Inspect the complete frozen PAPER 01
capital boundary end to end:

`Strategy state/restart → pending handoff → persisted TradeIntent → PRE_FLIGHT
→ fresh broker/account facts → PRE_SUBMISSION → persisted authorization →
PENDING_SUBMISSION Order → OANDA normalization/identity → canonical Fill →
Position/Trade → broker protection → transaction ingestion/cursor →
reconciliation → restart/resume`.

Produce a compact matrix with exactly these columns:

`INVARIANT | AUTHORITY | ENFORCEMENT LOCATION | DB ENFORCEMENT | TEST | STATUS`

For every invariant, identify duplicated or missing authority; in-memory bypasses
of persisted authority; provider facts not bound to Deployment/account/Order/
Trade; cursor advancement before durable fact application; persisted state not
restored; mutations before safety proof; fail-open defaults; checks present only
in outer layers; and race/replay/restart bypasses. Explicitly include the
current F-R2 duplicate protection identity, F-R3 account binding, F-R4 restart
continuity, F-R5 cursor application, and F-R6 persisted authorization findings,
without limiting the matrix to them. End with only the smallest bounded
remediation set required to make every PAPER 01 invariant PASS. Do not redesign
the frozen contract, propose PAPER 02, touch F-07/F-09, reopen T004, or implement
anything.

## Concerns

- The repository is historically capable but has no PAPER runtime, Deployment,
  TradingAccount, live data frontier, OANDA trading client, or reconciliation
  implementation; these are expected bounded implementation gaps from the audit.
- Current canonical persistence/execution has a full-fill historical assumption;
  PAPER 01 must reject unexpected partial/ambiguous broker state rather than
  silently claim PAPER 02 support.
- Independent validation classified F-01/F-02/F-03/F-05/F-06 as PRODUCT
  BLOCKERs and F-07 as PRODUCT IMPORTANT; F-04 and F-08 were remediated. F-09 is
  VALIDATION/TOOLING DEBT because PostgreSQL evidence is unavailable and the
  repository has legacy pyright diagnostics. Per SoloFlow, the next T004
  remediation requires explicit developer approval before dispatch.
- Developer approved the T004 remediation circuit-breaker bypass, limited to the
  recorded runtime ownership, production composition, reconciliation, and
  heartbeat-safety blockers. F-04 and F-08 remain closed.
- Fresh targeted validation passed F-01/F-03/F-06 but left F-02 production
  composition and F-05 durable reconciliation repair as PRODUCT BLOCKERs. F-07
  remains an out-of-scope activation blocker and F-09 remains validation/tooling
  debt. No `READY_TO_ACTIVATE` state is justified.
- Developer approved a second T004 reopening strictly for F-02 production
  composition and F-05 durable reconciliation repair/cursor. Passed findings
  remain closed; F-07 and F-09 remain outside this remediation.
- Targeted validation passed F-02/F-05, but independent rereview found two
  unresolved CRITICAL safety findings: conflicting external Fill identity can be
  misattributed, and repair can apply an entry Fill without current broker-hosted
  protection proof. F-07 and F-09 also remain unresolved gates.
- Developer approved reopening T004 again, strictly for F-R1/F-R2. F-R1 requires
  same-Order and immutable provider-fact identity agreement on Fill deduplication;
  any collision must roll back, persist/surface a critical safety outcome, and
  block exposure. F-R2 requires exactly one matching current open OANDA Trade,
  matching Position identity/direction/full quantity, and matching broker-hosted
  stop and actual-Fill-derived target before a missed entry Fill or cursor is
  applied. Failed or incomplete proof returns `RECONCILIATION_REQUIRED` with
  cursor unchanged and no local entry application. Required regressions cover
  collision, absent/mis-protected Trade, one successful repair, replay
  idempotency, and cursor-after-durable-application. F-07 and F-09 remain
  carried-forward gates; no activation is authorized.
- Fresh targeted validation passed the reviewed F-R1/F-R2 implementation cases,
  conditional on unavailable PostgreSQL execution. Independent targeted rereview
  still found CRITICAL F-R1 (incomplete provider identity/collision-race guards)
  and CRITICAL F-R2 (incomplete protection quantities/repair-boundary freshness),
  plus IMPORTANT F-R2 regression-fixture cursor evidence. Per the developer's
  explicit stop instruction, do not reopen T004 or dispatch another worker until
  separately approved; preserve the remediation packets in REVIEW.md.
- Developer approved reopening T004 with a fresh BUILD worker/session strictly
  for the frozen F-R1/F-R2 contract: complete provider Fill identity agreement,
  uniqueness/race rollback and fresh re-read/collision handling; coherent
  current Trade/Position/protection proof, freshness, repair, and cursor safety;
  and the numeric OANDA transaction-ID fixture correction. Passed findings stay
  closed. F-07/F-09, activation, credentials, Risk policy, and PAPER 02 remain
  outside scope.
- Fresh targeted validation passed, but independent rereview found unresolved
  CRITICAL F-R1 provider Order-identity disagreement and CRITICAL F-R2
  immediate-protection Trade exposure proof defects, plus IMPORTANT loss of
  non-null Fill source-bar provenance. Per the developer's explicit stop rule,
  no further remediation is dispatched. F-07 and F-09 remain carried forward;
  activation and `READY_TO_ACTIVATE` are not authorized.
- Developer approved one narrow reopening of the current T004 BUILD worker for
  exactly the three REVIEW findings: reject conflicting compound provider Order
  identities as UNKNOWN before authoritative Fill normalization; retain and
  validate immediate post-Fill Trade identity, signed current/initial units,
  open state, and freshness; and persist every immutable canonical Fill fact,
  including `source_market_bar_id`, with a non-null replay regression. F-07,
  F-09, Risk policy, credentials, activation, and PAPER 02 remain untouched.
- Targeted validation passed the three approved fixes. Independent targeted
  rereview verified those fixes but found additional CRITICAL F-R2 duplicate
  stop/target provider identity, CRITICAL F-R3 account-binding, CRITICAL F-R5
  cursor-application, IMPORTANT F-R4 restart-continuity, and IMPORTANT F-R6
  persisted-Risk-approval defects. Per the explicit stop rule, do not broaden
  or dispatch another remediation; preserve these findings for separate
  approval. F-07 and F-09 remain carried forward.
- Developer placed PAPER 01 implementation on hold because the remediation loop
  is not converging. A fresh high-reasoning closure analysis is authorized only
  to inspect the complete capital boundary end to end and produce an
  `INVARIANT | AUTHORITY | ENFORCEMENT LOCATION | DB ENFORCEMENT | TEST | STATUS`
  matrix plus the smallest bounded remediation set. The frozen PLAN,
  ARCHITECTURE, and T004 reconciliation remain authoritative. Do not reopen
  T004, implement findings, broaden PAPER 01, add PAPER 02, or touch F-07/F-09.
- Existing audit and other pre-existing untracked paths must remain untouched.
- The developer subsequently froze `IMPLEMENTATION-CLOSURE.md` for BUILD and
  explicitly authorized only C001-C004. This updates execution phase/status; it
  does not alter the frozen PLAN/ARCHITECTURE semantics or T004 reconciliation.
  No substantive contradiction between C001-C004 and the higher-authority
  artifacts was identified before task creation; any contradiction discovered
  during BUILD requires an immediate stop rather than reinterpretation.
