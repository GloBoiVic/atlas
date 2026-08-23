import './globals.css';
import { Providers } from './providers';

export const metadata = { title: 'Atlas · Experiments' };

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
