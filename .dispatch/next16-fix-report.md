# Next.js 16 Final Review Fix Report

## Status

Complete on `chore/next16-upgrade`.

## Fixes

- Reworked `Dockerfile.frontend` into dependency, builder, and runtime stages.
- Reused the existing `npm ci` dependency installation during the build.
- Copied `public` and `.next/static` into the runtime image alongside `.next/standalone`.
- Preserved `NEXT_PUBLIC_API_URL` as a build argument and runtime environment variable.
- Kept Node `20.9-slim`, set the production runtime environment, and launched
  `.next/standalone/server.js` directly with Node.
- Added `tests/test_frontend_dockerfile.py`, a Docker-free static regression test for the
  standalone command and asset contract.
- Updated `CURRENT.md` branch and Next.js 16 status metadata.

## Residual Risk

`npm audit` continues to report the existing dependency vulnerabilities in the locked frontend
dependency tree. They were not introduced or changed by this fix. No audit overrides, package
additions, or dependency downgrades were made; remediation remains follow-up work.
