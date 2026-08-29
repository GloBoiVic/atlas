import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const fixture = JSON.parse(
  readFileSync('tests/e2e/.fixtures.json', 'utf8'),
) as {
  failedExperimentId: string;
  primarySnapshotId: string;
  invalidSnapshotId: string;
  zeroSnapshotId: string;
};

test.describe.configure({ mode: 'serial' });

async function configure(
  page: import('@playwright/test').Page,
  end = '2026-01-06T02:30',
) {
  await page.goto('/experiments/new');
  await expect(page.getByLabel('StrategyVersion')).toHaveValue(/.+/);
  await expect(page.getByLabel('DatasetSnapshot')).toHaveValue(/.+/);
  await page
    .getByLabel('DatasetSnapshot')
    .selectOption(fixture.primarySnapshotId);
  await expect(page.getByLabel('DatasetSnapshot')).toHaveValue(
    fixture.primarySnapshotId,
  );
  await setUtcDateTime(page, 'Trading start', '2026-01-06T01:00');
  await setUtcDateTime(page, 'Trading end', end);
  await expect(
    page.getByRole('button', { name: 'Validate coverage' }),
  ).toBeEnabled();
  await page.getByRole('button', { name: 'Validate coverage' }).click();
  await expect(
    page.getByText('The selected period is eligible to run.'),
  ).toBeVisible();
}

async function setUtcDateTime(
  page: import('@playwright/test').Page,
  label: string,
  value: string,
) {
  const [date, time] = value.split('T');
  const target = new Date(`${date}T00:00:00Z`);
  const monthLabel = target.toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const dateButton = page.getByRole('button', {
    name: new RegExp(`^${label} date`),
  });
  await dateButton.click();
  const calendar = page.getByRole('application', {
    name: 'Choose UTC date',
  });
  for (let month = 0; month < 24; month += 1) {
    if (await calendar.getByText(monthLabel, { exact: true }).isVisible())
      break;
    await calendar.getByRole('button', { name: 'Previous month' }).click();
  }
  await expect(calendar.getByText(monthLabel, { exact: true })).toBeVisible();
  await calendar.getByRole('button', { name: date }).click();
  await page.getByLabel(`${label} time in UTC`).selectOption(time);
}

test('configures, runs, inspects a Trade, and safely retries the terminal command', async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  await configure(page);
  await page.getByRole('button', { name: 'Run Experiment' }).click();
  await expect(
    page.locator('header .status').filter({ hasText: 'Completed' }),
  ).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole('heading', { name: 'Result' })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Equity curve' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Strategy evidence and diagnostics' }),
  ).toBeVisible();
  await expect(page.getByText(/Result schema/)).not.toBeVisible();
  await expect(page.getByText('Trades', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Trade 1' }).click();
  await expect(page.getByRole('heading', { name: 'Trade 1' })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Strategy evidence' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'TradeIntent rationale' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Setup facts' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Risk decision' }),
  ).toBeVisible();
  const tradeHeadingOrder = await page
    .locator('h1, h2, h3, h4, h5')
    .allTextContents();
  const headingPosition = (heading: string) =>
    tradeHeadingOrder.findIndex((value) => value.trim() === heading);
  expect(headingPosition('TradeIntent rationale')).toBeLessThan(
    headingPosition('Setup facts'),
  );
  expect(headingPosition('Setup facts')).toBeLessThan(
    headingPosition('Risk decision'),
  );
  expect(headingPosition('Risk decision')).toBeLessThan(
    headingPosition('Order and Fill'),
  );
  expect(headingPosition('Order and Fill')).toBeLessThan(
    headingPosition('Protection'),
  );
  expect(headingPosition('Protection')).toBeLessThan(
    headingPosition('Outcome'),
  );
  const riskDecision = page.locator(
    'section[aria-labelledby="risk-decision-heading"]',
  );
  await expect(
    riskDecision.getByText('APPROVED', { exact: true }).first(),
  ).toBeVisible();
  const executionLineage = page.getByText('Execution lineage', { exact: true });
  await expect(executionLineage).toBeVisible();
  await executionLineage.click();
  await expect(
    page.getByRole('heading', { name: 'Orders and events' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Fills' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Fill 1' })).toBeVisible();
  const lineage = page
    .locator('details')
    .filter({ hasText: 'Execution lineage' });
  await expect(lineage.locator('h5').first()).toBeVisible();
  await expect(lineage).not.toContainText('No Orders were recorded.');
  await expect(lineage).not.toContainText('No Fills were recorded.');
  await expect(page.getByText('FINANCING EXCLUDED')).toBeVisible();

  const experimentId = page.url().match(/experiments\/([^/]+)/)?.[1];
  expect(experimentId).toBeTruthy();
  const first = await request.post(
    `/atlas-api/api/v1/experiments/${experimentId}/run`,
  );
  const second = await request.post(
    `/atlas-api/api/v1/experiments/${experimentId}/run`,
  );
  expect(first.ok()).toBeTruthy();
  expect(second.ok()).toBeTruthy();
  expect((await second.json()).status).toBe('COMPLETED');
});

test('shows invalid coverage and prevents creation', async ({ page }) => {
  await page.goto('/experiments/new');
  await expect(page.getByLabel('StrategyVersion')).toHaveValue(/.+/);
  await expect(page.getByLabel('DatasetSnapshot')).toHaveValue(/.+/);
  await page
    .getByLabel('DatasetSnapshot')
    .selectOption(fixture.invalidSnapshotId);
  await expect(page.getByLabel('DatasetSnapshot')).toHaveValue(
    fixture.invalidSnapshotId,
  );
  await setUtcDateTime(page, 'Trading start', '2026-01-06T01:00');
  await setUtcDateTime(page, 'Trading end', '2026-01-06T02:00');
  await expect(
    page.getByRole('button', { name: 'Validate coverage' }),
  ).toBeEnabled();
  await page.getByRole('button', { name: 'Validate coverage' }).click();
  await expect(page.getByText('This period cannot run yet.')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Run Experiment' }),
  ).toBeDisabled();
});

test('renders a failed Experiment without partial results', async ({
  page,
}) => {
  await page.goto(`/experiments/${fixture.failedExperimentId}`);
  await page.getByRole('button', { name: 'Run Experiment' }).click();
  await expect(page.getByText('Failed')).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByText('No trustworthy full result was created.'),
  ).toBeVisible();
  await expect(page.getByText('Equity curve')).not.toBeVisible();
});

test('completes a valid zero-Trade period explicitly', async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto('/experiments/new');
  await expect(page.getByLabel('StrategyVersion')).toHaveValue(/.+/);
  await expect(page.getByLabel('DatasetSnapshot')).toHaveValue(/.+/);
  await page.getByLabel('DatasetSnapshot').selectOption(fixture.zeroSnapshotId);
  await expect(page.getByLabel('DatasetSnapshot')).toHaveValue(
    fixture.zeroSnapshotId,
  );
  await setUtcDateTime(page, 'Trading start', '2026-01-06T01:00');
  await setUtcDateTime(page, 'Trading end', '2026-01-06T01:15');
  await expect(
    page.getByRole('button', { name: 'Validate coverage' }),
  ).toBeEnabled();
  await page.getByRole('button', { name: 'Validate coverage' }).click();
  await expect(
    page.getByText('The selected period is eligible to run.'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Run Experiment' }).click();
  await expect(
    page.locator('header .status').filter({ hasText: 'Completed' }),
  ).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText('No Trades', { exact: true })).toBeVisible();
  await expect(
    page.getByText('No executed Trades for this Experiment.'),
  ).toBeVisible();
});

test('hands off a StrategyVersion and compares completed results without ranking', async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  const failedResponses: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.method()} ${request.url()}`);
  });
  page.on('response', (response) => {
    if (response.status() >= 400)
      failedResponses.push(`${response.status()} ${response.url()}`);
  });
  await page.goto('/strategies');
  await expect(page.getByRole('heading', { name: 'Strategies' })).toBeVisible();
  await page.locator('main table tbody a').first().click();
  await expect(
    page.getByRole('heading', {
      name: 'EMA Sweep Confirmation Break',
      exact: true,
    }),
  ).toBeVisible();
  const handoff = page.getByRole('link', {
    name: /Use .* for an Experiment/,
  });
  await expect(handoff.first()).toBeVisible();
  await handoff.first().click();
  await expect(
    page.getByRole('heading', { name: 'New Experiment' }),
  ).toBeVisible();
  await expect(page.getByLabel('StrategyVersion')).toHaveValue(/.+/);
  await expect(page.getByText('1 · StrategyVersion')).toBeVisible();
  await expect(
    page.getByText('2 · Requested period & data readiness'),
  ).toBeVisible();

  await page.goto('/experiments');
  await expect(
    page.getByRole('heading', { name: 'Experiments' }),
  ).toBeVisible();
  await expect(page.getByText('Loading Experiments…')).not.toBeVisible({
    timeout: 30_000,
  });
  const completedRows = page
    .locator('tbody tr')
    .filter({ hasText: 'Completed' });
  const completedCount = await completedRows.count();
  expect(completedCount).toBeGreaterThanOrEqual(2);
  expect(completedCount).toBeLessThanOrEqual(4);
  await completedRows.nth(0).getByRole('checkbox').check();
  await completedRows.nth(1).getByRole('checkbox').check();
  await page.getByRole('link', { name: /Compare selected/ }).click();
  await expect(
    page.getByRole('heading', { name: 'Experiment comparison' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Canonical metrics' }),
  ).toBeVisible();
  await expect(page.getByText(/winner|best|optimal|recommended/i)).toHaveCount(
    0,
  );
  await expect(
    page.getByRole('link', { name: 'Open result' }).first(),
  ).toBeVisible();
  const inspectTrades = page.getByRole('link', { name: 'Inspect Trades' });
  await expect(inspectTrades).toHaveCount(2);
  await inspectTrades.first().click();
  await expect(page).toHaveURL(/\/experiments\/[^/]+#trades-heading$/);
  await expect(page.getByRole('heading', { name: 'Trades' })).toBeVisible();
  // The empty active-load state is an intentional 404 handled by the API
  // client; no other browser console errors or transport failures are allowed.
  const unexpectedConsoleErrors = consoleErrors.filter(
    (message) => !message.includes('status of 404 (Not Found)'),
  );
  const unexpectedFailedResponses = failedResponses.filter(
    (response) => !response.includes('/historical-data/load-requests/active'),
  );
  expect(unexpectedConsoleErrors).toEqual([]);
  expect(unexpectedFailedResponses).toEqual([]);
  expect(failedRequests).toEqual([]);
});
