"use client";

import { useEffect, useState } from 'react';
import { getTimetables, type LearningProgress } from '@/lib/lesson-delivery-api';
import styles from './parent.module.css';

const STATUS = { completed: 'Delivered', in_progress: 'Learning', yet_to_learn: 'Yet to learn' } as Record<string, string>;

/** Real delivery progress for one child. A new profile has none until its first class. */
export function ProgressCard({ studentId, name }: { studentId: string; name: string }) {
  const [state, setState] = useState<{ progress: LearningProgress | null } | null>(null);
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { const result = await getTimetables(studentId); if (active) setState({ progress: result.learning_progress }); }
      catch { /* keep what we last showed */ }
      if (active) timer = setTimeout(poll, 10000);
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [studentId]);
  const progress = state?.progress;
  const delivered = progress?.modules.reduce((sum, m) => sum + m.delivered_lessons, 0) ?? 0;
  return <section className="card stack" aria-labelledby="progress-title">
    <h2 id="progress-title">Maths progress</h2>
    {!state && <p role="status" className="muted">Loading…</p>}
    {state && (!progress || delivered === 0) && <p role="status"><strong>No lessons delivered yet.</strong> {name}’s progress will appear here after the first class.</p>}
    {progress && delivered > 0 && <p role="status"><strong>{delivered} {delivered === 1 ? 'lesson' : 'lessons'} delivered</strong></p>}
    {progress && delivered > 0 && <ul className={styles.moduleList}>{progress.modules.filter(m => m.status !== 'yet_to_learn').map(m => <li key={m.module}>
      <span>Module {m.module}</span><span>{STATUS[m.status] ?? m.status} · {m.delivered_lessons}{m.expected_lessons ? ` of ${m.expected_lessons}` : ''} lessons</span>
    </li>)}</ul>}
    <p className="muted">This counts lessons delivered, not marks. Understanding will be checked separately.</p>
  </section>;
}
