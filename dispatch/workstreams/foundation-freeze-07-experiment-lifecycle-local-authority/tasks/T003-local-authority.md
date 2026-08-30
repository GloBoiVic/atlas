# T003 — Loopback peer and local-host authority

## Assignment

- Status: `DONE`
- Role: `BUILD`
- Workstream: `foundation-freeze-07-experiment-lifecycle-local-authority`
- Depends on: none
- Owns: global ASGI authority guard, supported Uvicorn startup, and tests

## Frozen requirements

Implement `ARCHITECTURE.md` §7. Install a global pre-routing ASGI middleware that
allows lifespan but dispatches HTTP only when the actual `scope["client"]` peer is
an admitted IPv4/IPv6 loopback address. Missing, malformed, non-IP, Unix-socket,
private/public, and non-loopback mapped peers all receive the stable
`403 LOCAL_PEER_REQUIRED` envelope.

Separately require HTTP `Host` / HTTP/2 `:authority` to be `localhost` or a numeric
loopback literal, ignoring only port; if both are present they must agree. Host
must never identify the peer, and forwarding headers must be ignored. Keep the
peer resolver injectable only through the application factory/test seam and absent
from production request input. Update the supported Atlas Uvicorn entrypoint to
disable proxy-header rewriting (`--no-proxy-headers` or equivalent).

Do not add authentication, proxy support, remote access, or deployment hardening.

## Required proof

Test actual scope peers for IPv4, IPv6, mapped, private/public, malformed, missing,
and non-IP cases; local/external authorities; spoofed forwarding headers; startup
configuration; and lifespan/test-client operation. Assert denied requests do not
reach routing.

## Completion receipt

BUILD must update this file with `DONE` or `DONE_WITH_CONCERNS`, list every changed
application/test/config path, and record task-level checks and concerns. Do not edit
role artifacts or another task artifact.

- Implemented `LocalAuthorityMiddleware` as a global pre-routing ASGI guard. It
  passes lifespan/non-HTTP scopes through, derives peer authority from the actual
  ASGI client tuple, admits only IPv4/IPv6 loopback (including loopback-mapped
  IPv4), and returns the stable `403 LOCAL_PEER_REQUIRED` envelope otherwise.
- Added local-only `Host`/`:authority` validation with port parsing, authority
  agreement checks, and no forwarding-header trust. Added the factory-only peer
  resolver seam and wired the guard into `create_app`.
- Updated the supported README Uvicorn command with `--no-proxy-headers` and
  documented the test seam. Existing TestClient API regression tests now use the
  explicit seam and local authority.

### Files changed

- `backend/api/local_authority.py`
- `backend/api/app.py`
- `backend/tests/test_local_authority.py`
- `backend/tests/test_api_health.py`
- `backend/tests/integration/test_api_experiments.py`
- `README.md`
- `dispatch/workstreams/foundation-freeze-07-experiment-lifecycle-local-authority/tasks/T003-local-authority.md`

### Checks / evidence

- `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test' uv run pytest backend/tests/test_api_health.py backend/tests/integration/test_api_experiments.py backend/tests/test_local_authority.py -q` — 46 passed; previously skipped PostgreSQL/API checks now pass.
- `uv run pytest -m "not integration and not external"` — 386 passed, 4 skipped, 42 deselected.
- Targeted Ruff format and lint checks — passed.
- `uv run pyright backend/api/local_authority.py` — 0 errors.
- Uvicorn help check confirms `--no-proxy-headers` is available; `git diff --check` passed.
- Authority tests cover loopback/non-loopback/mapped/malformed/missing peers,
  local/external/malformed authorities, Host/`:authority` agreement,
  forwarding-header spoofing, resolver seam, pre-routing denial, and lifespan.

### Concerns

- None. The PostgreSQL-backed authority/API checks passed against the dedicated
  `atlas_freeze07_test` database. Pytest reported only the existing Starlette
  deprecation and `price_analysis` mark warnings.

## Approved review remediation — R-002

Reject `%` zone/scope identifiers, including encoded scoped IPv6 forms, in both
actual peer and Host/`:authority` values before loopback parsing. Preserve valid
`::1`, IPv4 loopback, mapped loopback, and `localhost` behavior. Add focused
authority tests asserting scoped forms are denied without routing, then update
this receipt with checks and final status.

## Approved review remediation — R-002 completion

- Status: `DONE`
- Rejected `%` zone/scope identifiers before IP parsing for actual peers and
  HTTP `Host`/`:authority` values, including raw, bracketed, percent-encoded,
  and decoded scoped IPv6 forms. Existing numeric loopback, mapped loopback,
  and `localhost` behavior remains admitted.

### Remediation files changed

- `backend/api/local_authority.py`
- `backend/tests/test_local_authority.py`
- `dispatch/workstreams/foundation-freeze-07-experiment-lifecycle-local-authority/tasks/T003-local-authority.md`

### Remediation checks / evidence

- `uv run pytest backend/tests/test_local_authority.py -q` — 42 passed;
  scoped peer and both `Host`/`:authority` forms return 403 and do not reach
  routing.
- `uv run pytest backend/tests/test_api_health.py -q` — 4 skipped because the
  dedicated PostgreSQL test database was not configured; existing Starlette
  deprecation warning only.
- Targeted Ruff check and format check passed.
- Targeted `git diff --check` passed.

### Final concerns

- None.
