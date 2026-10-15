"use client";

import { useCallback, useEffect, useState } from "react";

import { type AuthStatus, getAuthStatus } from "@/lib/api";

/** Who is signed in, and whether first-run setup has happened. `status` is null while loading. */
export function useAuthStatus() {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [error, setError] = useState(false);

  const load = useCallback(
    () =>
      getAuthStatus().then(
        (s) => {
          setStatus(s);
          setError(false);
        },
        () => setError(true),
      ),
    [],
  );

  useEffect(() => {
    load();
  }, [load]);

  return { status, error, refresh: load };
}
