# R001 VALIDATION — Confirmed Fill invariant visibility

- **Status:** PASS
- **Role:** VALIDATE
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Origin:** `REVIEW.md` C-001
- **Scope:** Independent validation of the bounded R001 remediation only. Earlier workstream `VALIDATION.md` and `REVIEW.md` remain immutable.

## Receipt

R001 is validated PASS. Once OANDA reports a matching full `tradeOpened` Fill,
the worse-than-bound, wrong-side Stop-geometry, and actual-risk-budget branches
all return `FILLED_PROTECTION_INCOMPLETE`, retain the normalized Fill facts and
transaction provenance, and do not fall through to protection completion.
`UNKNOWN` remains reserved for entry uncertainty.

## Deterministic regression evidence

Command:

```text
uv run pytest backend/tests/paper/test_execution_composition.py backend/tests/integrations/test_oanda_entry_mutation.py backend/tests/integrations/test_oanda_execution_translation.py backend/tests/integrations/test_oanda_protection_completion.py -q
```

Result: **37 passed**.

The composition regression covers:

- worse-than-bound Fill at `1.10021` → `ENTRY_FILL_BOUND_VIOLATION`;
- wrong-side Stop geometry at `1.09490` →
  `ENTRY_FILL_STOP_GEOMETRY_VIOLATION`;
- actual risk `98.07300` against a patched budget of `90` →
  `ENTRY_FILL_RISK_BUDGET_EXCEEDED`.

For all three cases, assertions retain broker Order `1001`, Fill transaction
`1002`, Trade `7001`, actual Fill price/risk, transaction IDs `("1001",
"1002")`, and last transaction `1002`; outcome is not `UNKNOWN`, entry POST
count is one, and protection/target mutation count is zero. The focused entry
suite also verifies no second entry POST for one attempt.

## Changed-file checks

- `uv run ruff format --check` on `execution.py`,
  `execution_application.py`, and `test_execution_composition.py`: **PASS**.
- `uv run ruff check` on those changed files: **PASS**.
- `uv run pyright` on those changed files: **0 errors, 0 warnings**.
- `git diff --check` plus no-index checks for the untracked changed files:
  **PASS; no whitespace errors**.

## Capital-boundary evidence

All evidence is deterministic and uses injected fakes/`httpx.MockTransport`.
No real OANDA request, credential, broker mutation, retry, resubmission, or
capital-capable activation was performed.

## Concerns

The worktree contains inherited PAPER 04 changes outside this remediation;
they were not modified or revalidated as part of this receipt. Durable
reconciliation remains outside R001 and within the frozen PAPER 05 boundary.
