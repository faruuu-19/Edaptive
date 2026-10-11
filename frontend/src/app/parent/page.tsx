"use client";

import { ParentGate } from "@/features/auth";
import { ProfileManager } from "@/features/home-profile";

export default function Parent() {
  return (
    <main className="page">
      <ParentGate>
        <ProfileManager />
      </ParentGate>
    </main>
  );
}
