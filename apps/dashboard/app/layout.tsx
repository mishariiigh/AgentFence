import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Sidebar } from "@/components/sidebar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AgentFence — AI Agent Security Platform",
  description:
    "Scan. Test. Protect. Monitor. Local-first AI agent security engineering platform.",
};

// Explicit props type instead of Next.js's generated `LayoutProps<"/">`:
// the generated helper only exists after `next typegen`/a build produces
// `.next/types`, so a bare `tsc --noEmit` (as CI runs before any build) would
// fail with TS2304. A plain `children` prop preserves identical runtime
// behavior and does not depend on generated artifacts.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-x-hidden px-6 py-8 md:px-10">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
