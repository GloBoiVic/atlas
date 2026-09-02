# T001 — PAPER 01G OANDA Practice Risk Account-State Projection

- **Workstream:** `paper-01g-oanda-practice-risk-account-state-projection`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Owned artifact:** `dispatch/workstreams/paper-01g-oanda-practice-risk-account-state-projection/tasks/T001-paper-01g-oanda-practice-risk-account-state-projection.md`
- **Branch:** `solo/paper-01g-oanda-practice-risk-account-state-projection`
- **Base SHA:** `77f2b265a8833c9aed9f52664eab8efefe42e1f9`

## Objective

Implement the smallest deterministic bridge:

```text
OandaPracticeAccountSummarySnapshot
        ↓
pure projection
        ↓
AccountState
```

The only mapping is:

```python
AccountState(
    base_currency=summary.identity.base_currency,
    equity=summary.nav,
)
```

## Approved scope

Expected product/test changes:

- `backend/integrations/oanda/risk_projection.py`
- `backend/integrations/oanda/__init__.py` only if package export convention requires it
- `backend/tests/integrations/test_oanda_risk_projection.py`

Use a pure function accepting an existing `OandaPracticeAccountSummarySnapshot`. Do not add I/O, settings, credentials, HTTP/network machinery, requests, normalization, Risk evaluation, lifecycle/activation semantics, persistence, execution, runtime, API/UI, reconciliation, broker mutation, or generic broker architecture. Do not change `AccountState` or the OANDA account-summary contract.

## Required behavior

- Map `summary.identity.base_currency` exactly to `AccountState.base_currency`.
- Map `summary.nav` exactly to `AccountState.equity`.
- Preserve positive, zero, and negative finite NAV without rejection, clamping, `abs`, `None`, fallback, or recomputation.
- Ignore provider metadata, balance, P/L, margins, counts, and transaction ID.
- Do not consume pricing, open Trade/Position, pending Order, or any other PAPER fact.
- Do not mutate the frozen source snapshot.

## Required focused tests

Cover at least:

1. exact NAV mapping where `balance != nav`;
2. exact base-currency mapping;
3. positive, zero, and negative NAV preservation;
4. `margin_available != nav` still maps equity from NAV;
5. irrelevant source-field changes leave the projected `AccountState` unchanged;
6. source snapshot immutability;
7. pure/no-request/no-Risk-evaluation behavior by construction.

## Task-level checks

Run the focused projection/account/Risk test set and targeted Ruff, Pyright, and `git diff --check` checks described by the approved `PLAN.md`. Do not broaden validation unless the actual diff demonstrates a broader blast radius.

## Completion receipt

The BUILD worker must replace this assignment state with a complete receipt after implementation and task-level checks. Do not edit completed evidence after the task is marked `DONE`.

## BUILD receipt

- **Status:** `DONE`
- **Implementation:** Added the pure `project_oanda_practice_account_state` function, mapping only normalized OANDA `identity.base_currency` and `nav` into the existing Risk `AccountState`.
- **Package export:** Exported the projection through `backend.integrations.oanda` following the existing package convention.
- **Focused tests:** Added coverage for exact NAV/currency mapping, positive/zero/negative NAV preservation, irrelevant-field independence, source immutability, and deterministic repeated projection.
- **Files changed:**
  - `backend/integrations/oanda/risk_projection.py`
  - `backend/integrations/oanda/__init__.py`
  - `backend/tests/integrations/test_oanda_risk_projection.py`
- **Checks:**
  - `uv run pytest backend/tests/integrations/test_oanda_risk_projection.py backend/tests/integrations/test_oanda_account.py backend/tests/risk/test_service.py` — **60 passed**
  - Targeted `uv run ruff format --check` — passed
  - Targeted `uv run ruff check` — passed
  - Targeted `uv run pyright` — **0 errors, 0 warnings, 0 informations**
  - `git diff --check` — passed
- **Concerns:** None.
