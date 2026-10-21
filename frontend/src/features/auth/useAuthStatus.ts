"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AUTH_CHANGED_EVENT, type AuthStatus, getAuthStatus } from "@/lib/api";

/** Who is signed in, and whether first-run setup has happened. `status` is null while loading. */
export function useAuthStatus() {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [error, setError] = useState(false);
  const sequence = useRef({ id: 0 });

  const load = useCallback(
    () => {
      const requestId = ++sequence.current.id;
      return getAuthStatus().then(
        (s) => {
          if (requestId !== sequence.current.id) return;
          setStatus(s);
          setError(false);
        },
        () => { if (requestId === sequence.current.id) setError(true); },
      );
    },
    [],
  );

  useEffect(() => {
    const counter = sequence.current;
    void load();
    const refresh = () => { void load(); };
    const storage = (event: StorageEvent) => { if (event.key === AUTH_CHANGED_EVENT) refresh(); };
    window.addEventListener('focus', refresh);
    window.addEventListener(AUTH_CHANGED_EVENT, refresh);
    window.addEventListener('storage', storage);
    return () => {
      counter.id++;
      window.removeEventListener('focus', refresh);
      window.removeEventListener(AUTH_CHANGED_EVENT, refresh);
      window.removeEventListener('storage', storage);
    };
  }, [load]);

  return { status, error, refresh: load };
}
