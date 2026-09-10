# Atlas

Atlas is a single-user algorithmic trading platform for controlled, reproducible research and guarded OANDA Practice PAPER operation.

Atlas prioritizes correctness, reproducibility, capital safety, simplicity, auditability, and trader control over speculative abstraction or scale.

## Sources of truth

Use each source only for the question it owns.

- **Desired change:** the approved active task/workstream.
- **Current implementation behavior:** code, nearby tests, schemas/migrations, and generated contracts.
- **Durable trading semantics:** `DOMAIN.md`.
- **Setup, operation, and supported user workflow:** `README.md`.
- **Historical reasoning:** closed `dispatch/` workstreams and Git history, only when explicitly needed.

Historical workstreams describe what happened at that time. They are not current specifications.

If prose conflicts with current implementation, do not silently make code match stale prose. Determine which source owns the question and surface genuine contradictions.

## Progressive context loading

For implementation work:

1. Read this file.
2. Read the approved active workstream/task.
3. Inspect the affected implementation and nearby tests.
4. Inspect relevant schemas and migrations when persistence is involved.
5. Consult only applicable sections of `DOMAIN.md`.
6. Consult `README.md` when setup, runtime, or supported workflow matters.
7. Load closed workstreams or Git history only for explicit regression, provenance, or rationale investigation.

Do not bulk-load historical documentation.

Do not create a parallel prose representation of the application.

## Repository map

- `backend/domain/` — core typed domain values and contracts.
- `backend/strategies/` — Strategy contracts, registration, provenance, and implementations.
- `backend/experiments/` — deterministic historical Experiment execution.
- `backend/market_data/` — historical market-data acquisition, validation, and provenance.
- `backend/risk/` — centralized Risk decisions.
- `backend/execution/` — execution-domain behavior and Fill application.
- `backend/integrations/` — external provider boundaries, currently including OANDA historical data.
- `backend/persistence/` — SQLAlchemy persistence and Alembic migrations.
- `backend/api/` — FastAPI application and HTTP contracts.
- `backend/runtime/` — runtime process boundary.
- `frontend/` — Next.js trader interface.
- `backend/tests/` and `tests/e2e/` — executable behavior and workflow evidence.
- `dispatch/` — active and historical SoloFlow workstreams.

## Current boundary

Committed `main` supports historical EUR/USD research using OANDA Practice historical data, immutable DatasetSnapshots, deterministic Experiments, centralized Risk, simulated execution, and inspectable Trade/results evidence, plus guarded OANDA Practice PAPER execution/runtime/activation/reconciliation capability.

Atlas is currently undeployed. Development-era prototype compatibility is not automatically permanent; retain it only when current behavior, deliberately retained evidence, or an explicit transition requires it.

PAPER capability remains guarded: starting Atlas, starting `atlas-runtime`, inspecting broker state, or possessing configured credentials does not authorize trading. LIVE broker execution is not a committed-main capability. Do not infer a future capability from historical workstreams.

## Engineering rules

- Implement the narrowest complete slice required by the approved task.
- Prefer explicit, typed, local abstractions over speculative frameworks.
- Do not generalize for future brokers, instruments, Strategies, users, workers, or deployment models unless the current task requires it.
- Preserve existing domain meaning unless the task explicitly changes it.
- Add or change dependencies only when the current stack cannot reasonably satisfy the requirement.
- Keep external provider payloads behind normalization boundaries.
- Keep credentials in ignored environment files. Never persist or log secrets.
- Treat unknown, stale, contradictory, partial, or failed financial state explicitly. Do not convert uncertainty into success.

### Provider-first

Before Atlas derives, reconstructs, hard-codes, or maintains a market, account, execution, pricing, conversion, margin, instrument, or transaction fact, determine whether the provider already exposes the authoritative fact. Prefer normalized provider truth. Atlas should own Atlas decisions, not duplicate the broker's ledger or market metadata. This is an engineering rule, not a reason to generalize provider infrastructure.

### Complexity ratchet

Generated files are exempt. For hand-maintained production code:

- A new module should normally target approximately 400 lines or fewer.
- A new module above approximately 600 lines requires explicit PLAN justification based on cohesion.
- An existing file at or above 800 lines must not receive a new responsibility without extracting a cohesive boundary.
- An existing file at or above 800 lines should not grow by more than approximately 50 net lines unless the PLAN explicitly explains why the behavior belongs there.
- For files above 1,200 lines, separable new behavior should normally be implemented in a new cohesive module rather than extending the existing file.
- These are ratchets, not automatic refactor triggers. Do not split a cohesive state machine merely to satisfy a line count.
- Every future Feature/Critical PLAN should identify expected files to modify/create and call out any large-file growth exception.

## Trading boundaries

`DOMAIN.md` contains the permanent Atlas trading laws.

In particular, do not bypass:

- Strategy/Risk separation;
- immutable StrategyVersion methodology;
- completed-data and no-lookahead requirements;
- Fill-derived exposure;
- explicit market-data provenance;
- fail-closed financial uncertainty;
- broker authority and reconciliation requirements when broker execution exists.

## Validation

Run the smallest relevant checks during development, then the appropriate completion gates for the changed slice.

```bash
uv sync --all-groups
npm ci

uv run alembic upgrade head
uv run alembic current
uv run alembic check

uv run ruff format --check backend
uv run ruff check backend
uv run pyright backend

uv run pytest -m "not integration and not external"
ATLAS_TEST_DATABASE_URL=<dedicated *_test database> uv run pytest -m integration

npm run check:web
npm run test:e2e
```

### Temporary Pyright baseline policy

- The repository-wide `uv run pyright backend` result is a recorded baseline, not a
  clean gate. Record its total errors, warnings, and informations truthfully.
- For every touched production Python file, compare focused structured Pyright output
  before and after the change using the same locked environment. The change must add
  no diagnostic absent from that file's baseline; an isolated clean surface must
  remain at zero diagnostics.
- Apply the same no-new-diagnostics comparison to touched test files against their
  test-file baseline.
- A valid structured report with a diagnostic exit status is distinct from a
  command/runtime failure. Report missing or invalid output, tool failures, and
  `uv` failures separately.
- Do not disable a Pyright rule or change Pyright configuration or lock state merely
  to make this baseline green.

Integration tests must use a dedicated PostgreSQL test database.

External credentialed checks are separate and must not be treated as ordinary test-suite prerequisites.

## Capital boundary

Code inspection, planning, deterministic tests, mocks, recorded provider-shape tests, migrations, and read-only checks do not authorize capital exposure.

Creating or changing broker credentials, activating PAPER/LIVE, changing Risk policy, submitting capital-capable broker requests, or otherwise changing exposure requires explicit trader authorization.
