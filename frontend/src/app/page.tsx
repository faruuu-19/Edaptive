"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuthStatus } from "@/features/auth";
import { ProfilePicker } from "@/features/home-profile";

export default function Start() {
  const router = useRouter();
  const { status, error } = useAuthStatus();

  useEffect(() => {
    if (!status) return;
    if (!status.setup_complete) router.replace("/setup");
    else if (status.actor?.role === "student") router.replace("/home");
  }, [status, router]);

  return (
    <main className="page">
      {error && <p className="error">Can&apos;t reach the backend. Start it with `make dev-backend`.</p>}
      {status?.setup_complete && status.actor?.role !== "student" && <ProfilePicker />}
    </main>
  );
}
