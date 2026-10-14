import { connection } from 'next/server';
import { notFound } from 'next/navigation';
import { LessonDemo } from '@/features/lesson-player';
export default async function Page() {
  await connection();
  if (process.env.EDAPTIVE_VOICE_PREVIEW !== '1' || !process.env.EDAPTIVE_DEMO_JOB_ID) notFound();
  return <main className="page"><LessonDemo /></main>;
}
