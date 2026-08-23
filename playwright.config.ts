import { defineConfig } from '@playwright/test';

const lifecycleDiagnostic = process.env.ATLAS_E2E_LIFECYCLE_DIAGNOSTIC === '1';
const runnerDiagnostic = process.env.ATLAS_E2E_RUNNER_DIAGNOSTIC === '1';
const diagnostic = lifecycleDiagnostic || runnerDiagnostic;

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/e2e/global-setup.ts',
  webServer: [
    {
      command: `.venv/bin/uvicorn ${diagnostic ? 'backend.tests.e2e_app:create_app' : 'backend.api.app:create_app'} --factory --host 127.0.0.1 --port 8000`,
      url: 'http://127.0.0.1:8000/health/ready',
      reuseExistingServer: false,
      env: {
        ATLAS_DATABASE_URL: process.env.ATLAS_E2E_DATABASE_URL ?? '',
        ...(lifecycleDiagnostic ? { ATLAS_E2E_LIFECYCLE_DIAGNOSTIC: '1' } : {}),
        ...(runnerDiagnostic ? { ATLAS_E2E_RUNNER_DIAGNOSTIC: '1' } : {}),
      },
      stdout: diagnostic ? 'pipe' : 'ignore',
    },
    {
      command: 'npm run dev:web',
      url: 'http://127.0.0.1:3000',
      reuseExistingServer: false,
      env: { ATLAS_API_BASE_URL: 'http://127.0.0.1:8000' },
    },
  ],
  use: {
    baseURL: 'http://127.0.0.1:3000',
    timezoneId: 'UTC',
  },
});
