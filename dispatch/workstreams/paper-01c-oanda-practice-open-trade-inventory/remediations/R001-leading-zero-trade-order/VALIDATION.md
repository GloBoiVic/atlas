# VALIDATION — R001 Leading-Zero Trade Order

- **Status:** `PASS`
- **Workstream:** `paper-01c-oanda-practice-open-trade-inventory`
- **Branch:** `solo/paper-01c-oanda-practice-open-trade-inventory`
- **Role:** `VALIDATE`
- **Remediation:** `R001`
- **Origin artifact:** `dispatch/workstreams/paper-01c-oanda-practice-open-trade-inventory/VALIDATION.md`

## Validation assignment

Independently verify that R001 resolves IMPORTANT V-001 without changing the
approved PAPER 01C contracts or scope:

- opposite provider array permutations containing accepted numerically equal,
  leading-zero Trade IDs normalize identically;
- raw provider Trade IDs remain preserved and exact duplicate IDs remain rejected;
- the focused OANDA test suite, targeted Ruff/Pyright, and `git diff --check`
  pass;
- no forbidden financial-domain, persistence, API/UI, runtime, Risk, execution,
  reconciliation, activation, broker mutation, or later-PAPER behavior was added.

Use the focused command from the original validation instruction:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_source.py
```

## Worker Evidence

### Environment and scope

- CWD and repository root verified as `/Users/vike/Desktop/atlas`.
- Branch verified as `solo/paper-01c-oanda-practice-open-trade-inventory`.
- No application, test, fixture, or scope changes were made by VALIDATE.

### Remediation verification

- `_trade_id_sort_key(...)` now orders by normalized numeric magnitude and uses
  the preserved raw provider Trade ID as a deterministic tie-breaker. Distinct
  accepted IDs such as `"01"` and `"1"` therefore have a total order independent
  of provider array order.
- The regression test
  `test_leading_zero_trade_ids_have_total_permutation_invariant_order` compares
  opposite permutations, verifies normalized inventory equality, and confirms
  raw IDs remain `("01", "1")`.
- Exact duplicate raw IDs remain rejected before ordering; no provider ID
  acceptance or rewriting changed.
- The existing provider-only contract and forbidden-scope boundaries remain
  unchanged. No Atlas financial-domain state, persistence, API/UI, runtime,
  Risk, execution, reconciliation, activation, broker mutation, or later-PAPER
  behavior was added.

### Checks

- Focused OANDA suite — **117 passed**:

  ```bash
  uv run pytest \
    backend/tests/integrations/test_oanda_trades.py \
    backend/tests/integrations/test_oanda_account.py \
    backend/tests/integrations/test_oanda_source.py
  ```

- Targeted Ruff format check — **passed**.
- Targeted Ruff lint check — **passed**.
- Targeted Pyright — **0 errors, 0 warnings, 0 informations**.
- `git diff --check` and no-index whitespace checks for the new implementation,
  test, and remediation receipt — **passed**.

## Conclusion

R001 **PASS**. IMPORTANT V-001 is resolved: accepted leading-zero Trade IDs now
normalize with permutation-invariant total ordering while preserving raw IDs and
exact duplicate rejection. No unresolved validation findings remain.
