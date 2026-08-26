# TASK-12 — CSS runtime/browser validation receipt

## Scope and safety

**Completed read-only inspection.** No application, dependency, Strategy, PAPER,
CSS, or Git files were changed. No OANDA request was made or retried. This
receipt is the only artifact written by this task.

## Runtime under test

- Route: `http://localhost:3000/experiments/new`
- Browser tab: `tab-18` (existing session), plus direct asset tab `tab-20`
- Observed page title: `Atlas · Experiments`
- Dev server: Next development runtime on localhost

## Stylesheet/build evidence

Source wiring is present and coherent:

- `frontend/app/layout.tsx:1` imports `./globals.css`.
- `frontend/app/globals.css:1` imports `tailwindcss` and defines the Atlas
  root/theme/component/compatibility rules.
- `frontend/postcss.config.mjs:1` enables `@tailwindcss/postcss`.
- The document's emitted stylesheet URL was
  `http://localhost:3000/_next/static/chunks/frontend_app_globals_1k5k-fl.css`.

Direct browser navigation to that emitted stylesheet succeeded with HTTP 200
(`text/css`, Next/Turbopack asset). Its visible response begins with the
compiled `globals.css` source marker and Tailwind layers. A separate HTTP
inspection of the same URL returned HTTP 200 and confirmed the emitted CSS
contains the following Atlas token/class occurrences:

| Compiled evidence | Occurrences |
|---|---:|
| `--atlas-color-background` | 3 |
| `--atlas-color-surface` | 17 |
| `--atlas-color-primary` | 18 |
| `--atlas-color-foreground` | 22 |
| `--atlas-color-negative` | 14 |
| `--atlas-color-focus-ring` | 2 |
| `.action-primary` | 5 |
| `.form-control` | 13 |
| `.nav-link` | 4 |

The compiled response includes concrete `--atlas-color-background: #07111f`
and declarations such as `.nav-link` using
`var(--atlas-color-foreground-muted)` and `.form-control` using
`var(--atlas-color-surface)`, `var(--atlas-color-control-border)`, and
`var(--atlas-color-foreground)`.

## Page/network/console evidence

For the inspected page (`tab-18`), the available network trace recorded:

| Browser epoch ms | Method | URL | Status |
|---:|---|---|---:|
| 1787712171057 | GET | `http://localhost:3000/atlas-api/health/ready` | 200 |
| 1787712171059 | GET | `http://localhost:3000/atlas-api/api/v1/experiments/configuration-options` | 200 |
| 1787712171059 | GET | `http://localhost:3000/atlas-api/api/v1/historical-data/capability` | 200 |
| 1787712171059 | GET | `http://localhost:3000/atlas-api/api/v1/historical-data/load-requests/active` | 404 |
| 1787712171062 | GET | `http://localhost:3000/atlas-api/health/ready` | 200 |
| 1787712171063 | GET | `http://localhost:3000/atlas-api/api/v1/experiments/configuration-options` | 200 |
| 1787712171063 | GET | `http://localhost:3000/atlas-api/api/v1/historical-data/capability` | 200 |
| 1787712171063 | GET | `http://localhost:3000/atlas-api/api/v1/historical-data/load-requests/active` | 404 |
| 1787712173506 | GET | `http://localhost:3000/__nextjs_font/geist-latin.woff2` | 200 |

The two `/active` 404s are the previously recorded API deployment mismatch;
they are not CSS/chunk failures. The duplicate API groups are consistent with
development Strict Mode remounting. The CSS asset itself was served 200 by the
direct browser navigation. The browser network diagnostic did not expose the
already-loaded document's stylesheet request as a separate entry, so a
browser-level stylesheet request record is not claimed beyond the direct 200
asset navigation.

Console diagnostics for `tab-18` were empty (zero entries, including errors and
warnings). Direct stylesheet tab `tab-20` also had zero console entries.

## Applied-style visual result

The page screenshot visibly shows the expected Atlas dark-first treatment:
deep blue-black canvas, dark navy bordered panels, cool light text, blue active
Experiments navigation/action treatment, and amber empty-state treatment. The
rendered controls and panels match the roles in the approved
`atlas-experiment-run-page.png`, `atlas-experiments-detail-page.png`, and
`atlas-experiments-page.png` references. This is positive evidence that the
compiled stylesheet is loaded and affecting the page, not an unstyled fallback.

## Computed-style limitation and diagnosis

The Local Host browser inspection surface available for this task provides page
text, accessibility snapshot, screenshot, console diagnostics, and network
summaries, but no computed-style/DOM-evaluation operation. Therefore exact
`getComputedStyle()` values for `body`, a `.form-control`, and an
`.action-primary` cannot be independently recorded here. Source and compiled
token presence is proven; computed-token resolution is **NOT VERIFIED** rather
than inferred.

The alleged “styling absent” condition was not reproduced. The screenshot and
compiled asset evidence show styles applied. No CSS/chunk request failure or
console failure was found. Consequently there is no exact runtime cause to
diagnose for absent styling. If an earlier visual inspection showed an
unstyled page, the safest conclusion is that it was invalid/stale as a CSS
runtime observation (for example, before the emitted asset completed or against
an old development document), not evidence of a current `globals.css` import
or PostCSS failure. This session cannot distinguish those historical timing
possibilities.

## Safe next step

Run one browser-capable computed-style probe against the loaded page (without
editing code): record `getComputedStyle(document.body).backgroundColor` and
`getComputedStyle()` values for a `.form-control` and `.action-primary`, plus
the resolved `--atlas-color-background`, `--atlas-color-surface`, and
`--atlas-color-primary` values. Separately triage the existing
`/api/v1/historical-data/load-requests/active` 404; do not hide or synthesize
that server status in the client.
