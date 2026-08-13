import { test, expect } from '@playwright/test';
test('foundation page', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('Atlas');
  await expect(page.getByRole('heading', { name: 'Atlas' })).toBeVisible();
});
