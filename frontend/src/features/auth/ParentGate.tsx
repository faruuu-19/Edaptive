"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { unlockParent } from "@/lib/api";

import { PinForm } from "./PinForm";
import { useAuthStatus } from "./useAuthStatus";

/** Shows `children` only to a signed-in parent; everyone else gets the PIN prompt. */
export function ParentGate({ children }: { children: ReactNode }) {
  const { status, error, refresh } = useAuthStatus();

  if (error) return <p className="error">Can&apos;t reach the backend. Is it running?</p>;
  if (!status) return null;
  if (status.actor?.role === "parent") return <>{children}</>;

  return (
    <div className="stack">
      <PinForm
        title="Parents only"
        hint="Enter your parent PIN to manage profiles and settings."
        submitLabel="Unlock"
        onSubmit={async (pin) => {
          await unlockParent(pin);
          await refresh();
        }}
      />
      <Link className="btn btn-quiet" href="/" style={{ textAlign: "center" }}>
        Back to profiles
      </Link>
    </div>
  );
}
