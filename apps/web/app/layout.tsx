import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Auto Video Sub",
  description: "Chinese-to-Vietnamese video localization",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <nav className="app-nav" aria-label="Application navigation">
          <a href="/">Workspace</a>
          <a href="/settings">AI settings</a>
        </nav>
        {children}
      </body>
    </html>
  );
}
