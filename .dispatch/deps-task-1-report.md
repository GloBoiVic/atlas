# Dependency Task 1 Report

## Status

Completed. Only the requested lockfiles and this report are intended for the task commit.

## Inputs

- Python manifest: `pyproject.toml`
- Frontend manifest: `frontend/package.json`
- Original manifest SHA-1 values:
  - `pyproject.toml`: `74ac571074f5ffc4a286f545e181eaf881e401be`
  - `frontend/package.json`: `86fede638a3adc6661a2e9fbafea274f97e5b81f`

## Generation

- Ran `/Users/vike/Library/Python/3.13/bin/uv lock` from the repository root.
  - Result: resolved 73 packages.
  - Generated: `uv.lock`.
- Ran `npm install` with npm 12.0.1 from `frontend/`.
  - Result: added 342 packages and audited 343 packages.
  - Generated: `frontend/package-lock.json`.
- The npm 12 fallback was not required.

## Checks

- `/Users/vike/Library/Python/3.13/bin/uv lock --check`: passed.
- `/Users/vike/Library/Python/3.13/bin/uv tree --depth 1`: passed; resolved project and dev dependencies are represented in the lockfile.
- `npm ci --dry-run --ignore-scripts`: passed.
- Compared `package-lock.json` root `dependencies` and `devDependencies` with `package.json` using a semantic, key-order-independent comparison: passed.
- Recomputed manifest SHA-1 values after generation: unchanged from the original values above.
- Reviewed generated lockfile roots and dependency trees: no package was added to either manifest, and no manifest was modified.

## Generated Files

- `uv.lock` (2,276 lines)
- `frontend/package-lock.json` (6,533 lines)

## Concerns

- `npm install` reported 3 high-severity audit findings in the resolved frontend tree, involving Next.js and transitive PostCSS/sharp packages. Resolving them would require dependency or manifest changes, which are outside this task.
- npm blocked install scripts for `unrs-resolver` and `sharp` under its current install-script policy. This did not prevent lockfile generation or the dry-run consistency check.
- The worktree contained unrelated pre-existing changes in `.dispatch/ledger.md` and untracked dependency brief files. They were not included in the task changes.

## Correction Note

- Corrected the original manifest SHA-1 values using the exact manifest contents from the parent commit of the lockfile-generation commit. No manifest or lockfile was modified.
