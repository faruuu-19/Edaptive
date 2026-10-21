"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuthStatus } from "@/features/auth";
import { PrepProgress, TodaysTimetable } from "@/features/lesson-player";
import { ChildHome } from "@/features/home-profile";
import { Meadow } from "@/features/theme";
import { getProfile, type Profile } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const { status } = useAuthStatus();
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    let active = true;
    if (!status) return;
    const studentId = status.actor?.role === "student" ? status.actor.student_id : null;
    if (!studentId) router.replace("/");
    else getProfile(studentId).then(p => { if (active) setProfile(p); }, () => { if (active) router.replace("/"); });
    return () => { active = false; };
  }, [status, router]);

  const currentProfile = status?.actor?.role === 'student' && profile?.id === status.actor.student_id ? profile : null;
  return <main className="page">{currentProfile && <ChildHome key={currentProfile.id} profile={currentProfile} mathsHref="/timetable" mathsNote={<PrepProgress studentId={currentProfile.id} />} aside={<TodaysTimetable studentId={currentProfile.id} />} />}{currentProfile && <Meadow />}</main>;
}
