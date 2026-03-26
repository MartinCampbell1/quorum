import type { Metadata } from "next";
import { Fira_Sans, Fira_Code } from "next/font/google";
import "./globals.css";

const firaSans = Fira_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

const firaCode = Fira_Code({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Quorum — Multi-Agent Orchestration",
  description: "Orchestrate AI agents with different collaboration modes",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${firaSans.variable} ${firaCode.variable} font-sans antialiased`}
        style={{
          backgroundColor: "var(--color-bg-primary)",
          color: "var(--color-text-primary)",
        }}
      >
        {children}
      </body>
    </html>
  );
}
