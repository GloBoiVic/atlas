import type { Metadata } from "next";
import { Toaster } from "sonner";

import { TopNav } from "@/components/layout/top-nav";
import { Providers } from "@/app/providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "Atlas",
  description: "Algorithmic trading platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <TopNav />
          <main>{children}</main>
          <Toaster position="bottom-right" theme="dark" />
        </Providers>
      </body>
    </html>
  );
}
