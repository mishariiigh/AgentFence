"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Status = "checking" | "online" | "offline";

export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    const check = () =>
      api
        .health()
        .then(() => !cancelled && setStatus("online"))
        .catch(() => !cancelled && setStatus("offline"));
    check();
    const interval = setInterval(check, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const label = {
    checking: "Checking API…",
    online: "API connected",
    offline: "API offline — run `agentfence dashboard`",
  }[status];

  return (
    <div
      className={cn(
        "mb-6 flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm",
        status === "online" && "border-emerald-500/30 bg-emerald-500/5 text-emerald-300",
        status === "offline" && "border-red-500/30 bg-red-500/5 text-red-300",
        status === "checking" && "border-border text-muted-foreground",
      )}
    >
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          status === "online" && "bg-emerald-400",
          status === "offline" && "bg-red-400",
          status === "checking" && "bg-zinc-400 animate-pulse",
        )}
      />
      {label}
    </div>
  );
}
