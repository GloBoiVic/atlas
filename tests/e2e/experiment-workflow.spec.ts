import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const fixture = JSON.parse(
  readFileSync('tests/e2e/.fixtures.json', 'utf8'),
) as {
  failedExperimentId: string;
  primarySnapshotId: string;
  zeroSnapshotId: string;
};

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
  await page.getByLabel('Trading start').fill('2026-01-06T01:00');
  await page.getByLabel('Trading end').fill(end);
  await expect(
    page.getByRole('button', { name: 'Validate coverage' }),
  ).toBeEnabled();
  await page.getByRole('button', { name: 'Validate coverage' }).click();
  await expect(
    page.getByText('The selected period is eligible to run.'),
  ).toBeVisible();
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
  await expect(page.getByText('Trades', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Trade 1' }).click();
  await expect(page.getByRole('heading', { name: 'Trade 1' })).toBeVisible();
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
    .selectOption(fixture.primarySnapshotId);
  await expect(page.getByLabel('DatasetSnapshot')).toHaveValue(
    fixture.primarySnapshotId,
  );
  await page.getByLabel('Trading start').fill('2026-01-06T01:00');
  await page.getByLabel('Trading end').fill('2026-01-06T02:00');
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
  await page.getByLabel('Trading start').fill('2026-01-06T01:00');
  await page.getByLabel('Trading end').fill('2026-01-06T01:15');
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
  await expect(page.getByText('No Trades', { exact: false })).toBeVisible();
  await expect(
    page.getByText('No executed Trades for this Experiment.'),
  ).toBeVisible();
});
