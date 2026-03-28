import type { Metadata } from "next";
import type { CSSProperties, ReactNode } from "react";
import { ThemeProvider } from "next-themes";
import "@xyflow/react/dist/style.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quorum",
  description: "Multi-agent orchestration",
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className="font-sans antialiased"
        style={
          {
            "--font-sans": '"Inter", "Geist", "SF Pro Display", system-ui, sans-serif',
            "--font-mono": '"JetBrains Mono", "SFMono-Regular", "SF Mono", ui-monospace, monospace',
          } as CSSProperties
        }
      >
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
