import { test, expect } from '@playwright/test';

const mutationControl =
  /\b(activate|stop|reconcile|buy|sell|close|order|trade|sl\/tp|resume|load|restart|revive|broker)\b/i;

async function blockMutationTraffic(page: import('@playwright/test').Page) {
  const attempted: string[] = [];
  await page.route('**/atlas-api/**', async (route) => {
    const request = route.request();
    if (!['GET', 'HEAD'].includes(request.method())) {
      attempted.push(`${request.method()} ${request.url()}`);
      await route.abort();
      return;
    }
    await route.continue();
  });
  return attempted;
}

function primaryNavigation(page: import('@playwright/test').Page) {
  return page.getByRole('navigation', { name: 'Primary' });
}

async function expectSurface(
  page: import('@playwright/test').Page,
  linkName: string,
  path: string,
  heading: string,
) {
  const navigation = primaryNavigation(page);
  await navigation.getByRole('link', { name: linkName, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`${path}/?$`));
  await expect(
    page.getByRole('heading', { name: heading, exact: true }),
  ).toBeVisible();
  await expect(
    navigation.getByRole('link', { name: linkName, exact: true }),
  ).toHaveAttribute('aria-current', 'page');
}

async function expectNoMutationControls(page: import('@playwright/test').Page) {
  const labels = await page.locator('button, a').allTextContents();
  expect(labels.filter((label) => mutationControl.test(label))).toEqual([]);
}

test('renders the Overview and navigates the read-only lifecycle shell', async ({
  page,
}) => {
  const attempted = await blockMutationTraffic(page);
  await page.goto('/');
  await expect(page).toHaveTitle('Atlas · Overview');
  await expect(
    page.getByRole('heading', { name: 'Overview', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
  await expect(page.getByText('API and database readiness')).toBeVisible();
  await expect(page.getByText('Strategy catalog')).toBeVisible();
  await expect(
    page.getByText(/returned items on the visible first page\./),
  ).toBeVisible();

  const navigation = primaryNavigation(page);
  for (const [name, path, heading] of [
    ['Strategies', '/strategies', 'Strategies'],
    ['Experiments', '/experiments', 'Experiments'],
  ] as const) {
    await expectSurface(page, name, path, heading);
  }

  await expectSurface(page, 'PAPER', '/paper', 'PAPER');
  await expect(page.getByText('PAPER capability')).toBeVisible();
  await expect(page.getByText('PAPER current status')).toBeVisible();
  await expect(
    page.getByText(/No active PAPER activation reported/),
  ).toBeVisible();
  await expect(
    page.getByText(/does not reconstruct historical activations/),
  ).toBeVisible();
  await expectNoMutationControls(page);

  await expectSurface(page, 'Data', '/data', 'Data');
  await expect(page.getByText('Historical data capability')).toBeVisible();
  await expect(page.getByText('Available DatasetSnapshots')).toBeVisible();
  await expect(page.getByText('Current historical load')).toBeVisible();
  await expect(page.getByText('No historical load is active.')).toBeVisible();

  await navigation.getByRole('link', { name: 'Overview', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole('heading', { name: 'Overview', exact: true }),
  ).toBeVisible();
  expect(attempted).toEqual([]);
});

test('keeps the primary navigation keyboard reachable on a narrow viewport', async ({
  page,
}) => {
  const attempted = await blockMutationTraffic(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/paper');
  await expect(
    page.getByRole('heading', { name: 'PAPER', exact: true }),
  ).toBeVisible();

  const navigation = primaryNavigation(page);
  await expect(navigation).toHaveClass(/overflow-x-auto/);
  await expect(navigation).toHaveClass(/min-w-0/);
  await expect(navigation).toHaveClass(/flex-1/);
  await expect(navigation).toHaveClass(/contain-paint/);
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.getByRole('link', { name: 'Atlas', exact: true }).focus();
  await page.keyboard.press('Tab');
  await expect(
    navigation.getByRole('link', { name: 'Overview', exact: true }),
  ).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(
    navigation.getByRole('link', { name: 'Strategies', exact: true }),
  ).toBeFocused();
  await expectNoMutationControls(page);
  expect(attempted).toEqual([]);
});
