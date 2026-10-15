import { ParentGate } from '@/features/auth';
import { ParentDashboard } from '@/features/parent';

export default async function Page({ params }: { params: Promise<{ studentId: string }> }) {
  const { studentId } = await params;
  return <main className="page"><ParentGate><ParentDashboard key={studentId} studentId={studentId} /></ParentGate></main>;
}
