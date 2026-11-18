"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import {
  Activity,
  FileSearch,
  FlaskConical,
  LayoutDashboard,
  ScrollText,
  Server,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/scans", label: "Security Scans", icon: FileSearch },
  { href: "/findings", label: "Findings", icon: Activity },
  { href: "/arena", label: "Attack Lab", icon: FlaskConical },
  { href: "/policies", label: "Policy Management", icon: ShieldCheck },
  { href: "/mcp", label: "MCP Inspection", icon: Server },
  { href: "/reports", label: "Reports", icon: ScrollText },
  { href: "/settings", label: "Settings", icon: Settings },
];

function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav className="flex-1 space-y-1 px-3">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              active
                ? "bg-sidebar-accent font-medium text-foreground"
                : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15">
          <ShieldCheck className="h-5 w-5 text-primary" />
        </div>
        <div>
          <div className="text-sm font-semibold tracking-tight">AgentFence</div>
          <div className="text-[11px] text-muted-foreground">
            Scan. Test. Protect. Monitor.
          </div>
        </div>
      </div>
      <Suspense fallback={<div className="flex-1" />}>
        <SidebarNav />
      </Suspense>
      <div className="border-t border-sidebar-border px-6 py-4">
        <div className="text-[11px] leading-relaxed text-muted-foreground">
          Local-first · No telemetry
          <br />
          Demo data only — not live results
        </div>
      </div>
    </aside>
  );
}
