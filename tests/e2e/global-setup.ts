import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

export default function globalSetup() {
  const fixtureFile = resolve('tests/e2e/.fixtures.json');
  execFileSync(resolve('.venv/bin/python'), ['-m', 'backend.tests.e2e_seed'], {
    cwd: resolve('.'),
    env: { ...process.env, ATLAS_E2E_FIXTURE_FILE: fixtureFile },
    stdio: 'inherit',
  });
}
