import { Timetable } from '@/features/lesson-player';
import { getMathsModules } from '@/lib/maths-modules';
export default async function Page({ searchParams }: { searchParams: Promise<{ listen?: string; student?: string }> }) {
  const { listen, student } = await searchParams;
  const mathsModules = await getMathsModules();
  return <main className="page"><Timetable autoStart={listen === '1'} studentId={student} mathsModules={mathsModules} /></main>;
}
