import { defineConfig } from '@playwright/test';

const lifecycleDiagnostic = process.env.ATLAS_E2E_LIFECYCLE_DIAGNOSTIC === '1';
const diagnostic = lifecycleDiagnostic;
const apiPort = process.env.ATLAS_E2E_API_PORT ?? '8000';
const webPort = process.env.ATLAS_E2E_WEB_PORT ?? '3000';
const apiBaseUrl = `http://127.0.0.1:${apiPort}`;
const webBaseUrl = `http://127.0.0.1:${webPort}`;

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/e2e/global-setup.ts',
  webServer: [
    {
      command: `.venv/bin/uvicorn ${diagnostic ? 'backend.tests.e2e_app:create_app' : 'backend.api.app:create_app'} --factory --host 127.0.0.1 --port ${apiPort}`,
      url: `${apiBaseUrl}/health/ready`,
      reuseExistingServer: false,
      env: {
        ATLAS_DATABASE_URL: process.env.ATLAS_E2E_DATABASE_URL ?? '',
        ...(lifecycleDiagnostic ? { ATLAS_E2E_LIFECYCLE_DIAGNOSTIC: '1' } : {}),
      },
      stdout: diagnostic ? 'pipe' : 'ignore',
    },
    {
      command: `npm run dev:web -- --port ${webPort}`,
      url: webBaseUrl,
      reuseExistingServer: false,
      env: { ATLAS_API_BASE_URL: apiBaseUrl },
    },
  ],
  use: {
    baseURL: webBaseUrl,
    timezoneId: 'UTC',
  },
});
