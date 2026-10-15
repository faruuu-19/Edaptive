import { Timetable } from '@/features/lesson-player';
export default async function Page({ searchParams }: { searchParams: Promise<{ listen?: string; student?: string }> }) {
  const { listen, student } = await searchParams;
  return <main className="page"><Timetable autoStart={listen === '1'} studentId={student} /></main>;
}
