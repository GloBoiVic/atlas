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

async function configure(
  page: import('@playwright/test').Page,
  end = '2026-01-06T02:30',
) {
  await page.goto('/experiments/new');
  await expect(page.getByLabel('Strategy')).toHaveValue(/.+/);
  await expect(page.getByLabel('Data').first()).toHaveValue(/.+/);
  await page.getByLabel('Data').first().selectOption(fixture.primarySnapshotId);
  await expect(page.getByLabel('Data').first()).toHaveValue(
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
  await expect(page.getByLabel('Strategy')).toHaveValue(/.+/);
  await expect(page.getByLabel('Data').first()).toHaveValue(/.+/);
  await page.getByLabel('Data').first().selectOption(fixture.invalidSnapshotId);
  await expect(page.getByLabel('Data').first()).toHaveValue(
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
  await expect(page.getByLabel('Strategy')).toHaveValue(/.+/);
  await expect(page.getByLabel('Data').first()).toHaveValue(/.+/);
  await page.getByLabel('Data').first().selectOption(fixture.zeroSnapshotId);
  await expect(page.getByLabel('Data').first()).toHaveValue(
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
