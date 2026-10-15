"use client";
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { deliveryAction, getTimetables, type SavedTimetable, type LearningProgress } from '@/lib/lesson-delivery-api';
import styles from './timetable.module.css';
import { needsMemoryHelp, preparationMessage } from './preparation-message';

const time = (ms: number) => new Intl.DateTimeFormat('en-PK', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' }).format(ms);
const date = (ms: number) => new Date(ms + 5 * 3600000).toISOString().slice(0, 10);
export function chooseDay(rows: SavedTimetable[]) {
  const today = rows[0] ? date(rows[0].server_now_ms) : '';
  return rows.find(row => row.status === 'active' && row.slots.some(s => s.class_phase === 'started'))
    ?? rows.find(row => row.school_date === today && row.status !== 'cancelled')
    ?? rows.find(row => row.status === 'active') ?? rows[0] ?? null;
}

export function DayPlan({ timetable }: { timetable: SavedTimetable }) {
  const isToday = timetable.school_date === date(timetable.server_now_ms);
  return <section className="stack" aria-label="Daily timetable">
    <div className="row spread"><h2>{isToday ? 'Today’s timetable' : 'Your next school day'}</h2><span className="muted">{timetable.school_date}</span></div>
    <ol className={styles.slots}>{timetable.slots.map(slot => {
      const minutes = Math.round((slot.end_ms - slot.start_ms) / 60000);
      const buffer = (slot.timing?.buffer_seconds ?? 0) / 60;
      const ready = slot.preparation?.status === 'ready';
      const coming = slot.kind === 'unavailable' || (slot.kind === 'lesson' && !ready && slot.class_phase !== 'completed');
      return <li key={slot.id} className={`${styles.slot} ${slot.kind === 'break' ? styles.breakSlot : ''}`}>
        <div className="stack" style={{ gap: 6 }}><strong>{slot.subject === 'math' ? 'Maths' : slot.title}{slot.module ? ` · Module ${slot.module}, Lesson ${slot.lesson}` : ''}</strong>
          {slot.kind === 'lesson' && <span>{slot.title}</span>}</div>
        <div className={styles.slotTime}><span>{time(slot.start_ms)} – {time(slot.end_ms)}</span><span>{minutes} minutes</span></div>
        <small>{slot.kind === 'break' ? 'Time to rest' : coming ? 'Coming soon' : slot.class_phase === 'completed' ? 'Lesson delivered' : slot.class_phase === 'started' ? 'In class' : 'Ready for class'}{slot.kind !== 'break' && ` · ${Math.max(0, minutes - buffer)} min lesson + ${buffer} min buffer`}{slot.timing?.basis === 'prepared_script' ? ' · Reviewed from the prepared script' : slot.kind !== 'break' ? ' · Provisional time' : ''}</small>
        {slot.kind === 'lesson' && !ready && <div className={styles.inlinePreparation}><label>Preparing lesson · {slot.preparation?.percent ?? 0}%<progress max="100" value={slot.preparation?.percent ?? 0} /></label><p className={needsMemoryHelp(slot.preparation) ? "notice" : "muted"} role={needsMemoryHelp(slot.preparation) ? "alert" : "status"}>{preparationMessage(slot.preparation)}</p></div>}
      </li>;
    })}</ol>
  </section>;
}

export function StudentDay({ studentId }: { studentId: string }) {
  const router = useRouter();
  const [day, setDay] = useState<SavedTimetable | null>(null);
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const [note, setNote] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { const result = await getTimetables(studentId); if (active) { setDay(chooseDay(result.timetables)); setProgress(result.learning_progress); setNote(result.routine?.message ?? 'Your parent can set your daily school start time.'); setLoaded(true); setError(''); } }
      catch { if (active) setError('Your timetable is temporarily unavailable. Trying again…'); }
      if (active) timer = setTimeout(poll, 1000);
    }
    void poll(); return () => { active = false; clearTimeout(timer); };
  }, [studentId]);
  const current = day?.slots.find(s => s.id === day.current_slot_id);
  async function action(kind: 'start' | 'borrow') {
    if (!day || !current) return;
    setBusy(true);
    try { const result = await deliveryAction({ timetableId: day.id, slotId: current.id }, kind); setDay(result); if (kind === 'start') router.push('/timetable?listen=1'); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="stack" style={{ gap: 24 }}>
    {error && <p className="error" role="alert">{error}</p>}
    {!loaded && !error && <p role="status">Loading your school day…</p>}
    {loaded && !day && <section className="card stack"><h2>Your school day</h2><p>{note}</p></section>}
    {day && <><DayPlan timetable={day} />{current?.class_phase === 'ringing' && <section className={`card stack ${styles.alarm}`} role="alert"><h2>It’s time for Maths!</h2><p>{current.preparation?.status === 'ready' ? 'Your lesson is ready. Come and join your class.' : 'Your lesson is still preparing. You can snooze for five minutes.'}</p><div className="row"><button className="btn btn-primary" disabled={busy || current.preparation?.status !== 'ready'} onClick={() => void action('start')}>Join class</button><button className="btn" disabled={busy} onClick={() => void action('borrow')}>Snooze 5 minutes</button></div></section>}{current?.class_phase === 'started' && <Link className="btn btn-primary" href="/timetable">Return to your class</Link>}<p className="muted">{note}</p></>}
    {progress && <details className="card"><summary className={styles.journeyTitle}>Your Maths journey</summary><ul className={styles.journey}>{progress.modules.map(module => <li key={module.module}><strong>Module {module.module}</strong><span>{module.status === 'completed' ? 'Delivered' : module.status === 'in_progress' ? 'Learning' : 'Yet to learn'} · {module.delivered_lessons}{module.expected_lessons ? ` of ${module.expected_lessons}` : ''} lessons delivered</span></li>)}</ul><p className="muted">Lesson delivery is recorded. Assessment mastery will be checked separately.</p></details>}
  </div>;
}
