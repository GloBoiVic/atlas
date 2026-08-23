import type { NextConfig } from 'next';

const apiBaseUrl = process.env.ATLAS_API_BASE_URL;

if (!apiBaseUrl || !/^https?:\/\/[^\s/]+(?:\/[^\s]*)?$/i.test(apiBaseUrl)) {
  throw new Error(
    'ATLAS_API_BASE_URL must be set to an absolute http(s) URL for the Atlas API.',
  );
}

const normalizedApiBaseUrl = apiBaseUrl.replace(/\/+$/, '');

const developmentOrigins =
  process.env.NODE_ENV === 'development' ? ['127.0.0.1'] : undefined;

const nextConfig: NextConfig = {
  // Local Playwright/dev traffic only; production builds do not allow origins.
  allowedDevOrigins: developmentOrigins,
  async rewrites() {
    return [
      {
        source: '/atlas-api/:path*',
        destination: `${normalizedApiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
