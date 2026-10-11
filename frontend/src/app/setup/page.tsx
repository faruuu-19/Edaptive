"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { PinForm, useAuthStatus } from "@/features/auth";
import { setupHousehold } from "@/lib/api";

export default function Setup() {
  const router = useRouter();
  const { status } = useAuthStatus();

  useEffect(() => {
    if (status?.setup_complete) router.replace("/");
  }, [status, router]);

  if (!status || status.setup_complete) return null;

  return (
    <main className="page page-narrow stack">
      <h1>Welcome to Edaptive</h1>
      <p className="muted" style={{ margin: 0 }}>
        First, choose a parent PIN. It keeps settings and profiles safe from little fingers.
        Everything stays on this computer.
      </p>
      <PinForm
        title="Create your parent PIN"
        hint="4 to 6 digits. You'll need it to manage profiles."
        confirm
        submitLabel="Create PIN"
        onSubmit={async (pin) => {
          await setupHousehold(pin);
          router.push("/parent");
        }}
      />
    </main>
  );
}
