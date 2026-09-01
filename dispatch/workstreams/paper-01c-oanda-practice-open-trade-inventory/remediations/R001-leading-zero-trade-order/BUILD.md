# R001 — Make provider Trade ordering permutation-invariant

- **Remediation ID:** `R001`
- **Status:** `DONE`
- **Workstream:** `paper-01c-oanda-practice-open-trade-inventory`
- **Origin finding:** `IMPORTANT V-001` in `dispatch/workstreams/paper-01c-oanda-practice-open-trade-inventory/VALIDATION.md`
- **Finding severity:** `IMPORTANT`
- **Related original task(s):** `T001`

## Approved requirement or invariant violated

PLAN acceptance criterion 8 requires provider array ordering not to affect
normalized equality. Valid positive-integer provider Trade IDs may contain
leading zeroes under the approved retained-ID contract. The current sort key
collides for numerically equal but textually distinct IDs, allowing stable-sort
input order to leak into the normalized tuple.

## Exact remediation outcome

Make deterministic ascending numeric provider Trade-ID ordering total and
permutation-invariant for all accepted IDs, including numerically equal
leading-zero representations, while preserving the provider-assigned raw ID
strings and rejecting exact duplicate IDs. Add a regression test that compares
opposite provider array orders containing such IDs.

## Affected implementation seams

- `backend/integrations/oanda/trades.py` — provider Trade inventory ordering.
- `backend/tests/integrations/test_oanda_trades.py` — ordering regression coverage.

## Explicit out-of-scope items

- Do not change provider ID acceptance or rewrite provider-assigned strings.
- Do not add Atlas Trade, Position, Order, Fill, ownership, reconciliation,
  persistence, API/UI, runtime, Risk, execution, broker mutation, or later-PAPER
  behavior.
- Do not change PAPER 01A/01B behavior or broaden the OANDA adapter boundary.

## Regression evidence required

- Opposite input permutations with distinct accepted IDs that have equal numeric
  value but different leading-zero text normalize identically.
- Existing focused OANDA tests remain passing.
- Targeted Ruff/Pyright and `git diff --check` pass.

## Worker Evidence

Updated the numeric Trade-ID sort key with a raw provider-ID tie-breaker. Accepted
leading-zero IDs retain their original strings, exact duplicate IDs remain rejected,
and numerically equal distinct IDs now have total deterministic ordering independent
of provider array permutation.

Added regression coverage comparing opposite permutations of `"01"` and `"1"`.

Checks and evidence:

- `uv run pytest backend/tests/integrations/test_oanda_trades.py backend/tests/integrations/test_oanda_account.py backend/tests/integrations/test_oanda_source.py` — **117 passed**;
- targeted `uv run ruff format --check ...` — **passed**;
- targeted `uv run ruff check ...` — **passed**;
- targeted `uv run pyright ...` — **0 errors, 0 warnings, 0 informations**;
- `git diff --check` — **passed**.

No persistence, API/UI, runtime, Risk, execution, reconciliation, broker mutation,
or PAPER 01A/01B behavior was changed.
