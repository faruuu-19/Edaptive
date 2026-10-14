import { Timetable } from '@/features/lesson-player';
export default async function Page({ searchParams }: { searchParams: Promise<{ listen?: string }> }) {
  const { listen } = await searchParams;
  return <main className="page"><Timetable autoStart={listen === '1'} /></main>;
}
