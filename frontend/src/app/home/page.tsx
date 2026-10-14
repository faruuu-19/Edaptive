"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuthStatus } from "@/features/auth";
import { StudentDay } from "@/features/lesson-player";
import { ChildHome } from "@/features/home-profile";
import { getProfile, type Profile } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const { status } = useAuthStatus();
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    if (!status) return;
    const studentId = status.actor?.role === "student" ? status.actor.student_id : null;
    if (!studentId) router.replace("/");
    else getProfile(studentId).then(setProfile, () => router.replace("/"));
  }, [status, router]);

  return <main className="page">{profile && <div className="stack" style={{ gap: 30 }}><ChildHome profile={profile} mathsHref="/timetable" /><StudentDay studentId={profile.id} /></div>}</main>;
}
