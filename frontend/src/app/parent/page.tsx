"use client";

import Link from "next/link";
import { ParentGate } from "@/features/auth";
import { ProfileManager } from "@/features/home-profile";

export default function Parent() {
  return (
    <main className="page">
      <ParentGate>
        <div className="stack"><ProfileManager /><Link className="btn btn-primary" href="/timetable">Plan lessons and timetable</Link></div>
      </ParentGate>
    </main>
  );
}
