import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';

const config = [...nextCoreWebVitals, ...nextTypescript];
const eslintConfig = [
  { ignores: ['**/.next/**', '**/node_modules/**'] },
  ...config,
  { rules: { '@next/next/no-html-link-for-pages': 'off' } },
];
export default eslintConfig;
