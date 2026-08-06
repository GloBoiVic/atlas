# Feature 10 Task 5 — Journal page-level UI

## Scope completed

- Added the dynamic `/journal` App Router route with server-side initial loading.
- Added route loading and error boundaries.
- Added typed `listJournalEntries` and `updateJournalNotes` API client functions, including
  optional UTC date and bot filters.
- Added responsive journal entry rows with identity, strategy, direction, entry/exit prices,
  quantity, P&L, timestamps, and progressive-disclosure signal/market context.
- Preserved API Decimal strings for display; the browser does not calculate P&L or metrics.
- Added empty, initial-load error, refresh error, and pending refresh states.
- Added notes-only editing through `PATCH /journal/{id}/notes`, with disabled unchanged saves,
  pending button state, and Sonner success/error notifications.
- Added the root Sonner host and updated `context/ui-registry.md` through the imprint workflow.

## Files

- `frontend/src/app/journal/page.tsx`
- `frontend/src/app/journal/journal-view.tsx`
- `frontend/src/app/journal/loading.tsx`
- `frontend/src/app/journal/error.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/app/layout.tsx`
- `context/ui-registry.md`

## Validation

- `npm run lint` — passed.
- `npm run typecheck` — passed.
- `npm run build` — passed; `/journal` is dynamically server-rendered.
- Frontend test runner — not configured in the project, so no automated UI tests were added.

## Scope guard

No navigation shell, dashboard integration, Trades page, Analytics page, bot controls, or
dispatch planning files were changed for this task. Existing unrelated working-tree changes were
left untouched and are not included in the Task 5 commit.

## Commit

`39ad47d` — `feat: add journal page UI`

## Reviewer fix

- Updated zero-P&L presentation to use string-safe Decimal matching. Values such as `0.00`,
  `0.000`, and `-0.0` now render neutrally without a `+` prefix; no API Decimal strings are
  parsed or recalculated.
- No frontend test harness exists, so no test was added.
- Re-ran `npm run lint`, `npm run typecheck`, and `npm run build`; all passed.
