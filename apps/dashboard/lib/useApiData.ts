"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";

export type RequestState = "loading" | "ready" | "error";

export interface AsyncState<T> {
  state: RequestState;
  data: T | null;
  error: string | null;
  reload: () => void;
}

/**
 * Small data-fetching hook with loading / error / reload handling.
 * Never substitutes demo data on failure — errors are surfaced.
 */
export function useApiData<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): AsyncState<T> {
  const [state, setState] = useState<RequestState>("loading");
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    // All state updates happen in promise callbacks (never synchronously in the
    // effect body), per react-hooks/set-state-in-effect.
    fetcher()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setState("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Unexpected error",
        );
        setState("error");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { state, data, error, reload };
}
