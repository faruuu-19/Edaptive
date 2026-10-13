import { connection } from "next/server";
import { notFound } from "next/navigation";
import { LessonPlayer } from "@/features/lesson-player";

export default async function Page() {
  await connection();
  if (process.env.EDAPTIVE_VOICE_PREVIEW !== "1") notFound();
  return <main className="page"><LessonPlayer /></main>;
}
