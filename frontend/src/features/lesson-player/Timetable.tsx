"use client";

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useAuthStatus } from '@/features/auth';
import { getProfile, listProfiles, type Profile } from '@/lib/api';
import { deliveryAction, getSchoolRoutine, getTimetables, saveSchoolStartTime, type SchoolRoutine, type SavedTimetable } from '@/lib/lesson-delivery-api';
import { LessonPlayer } from './LessonPlayer';
import styles from './timetable.module.css';
import { ChildClass } from './ChildClass';
import { DayPlan, chooseDay } from './DayPlan';
import { needsMemoryHelp, preparationMessage } from './preparation-message';
import { useRouter } from 'next/navigation';

const timeText = (ms: number) => new Intl.DateTimeFormat('en-PK', { timeZone: 'Asia/Karachi', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(ms);

export function Timetable({ autoStart = false }: { autoStart?: boolean } = {}) {
  const router = useRouter();
  const { status, error: authError, refresh } = useAuthStatus();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [student, setStudent] = useState('');
  const [routine, setRoutine] = useState<SchoolRoutine | null>(null);
  const [schedule, setSchedule] = useState<SavedTimetable | null>(null);
  const [startTime, setStartTime] = useState('');
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [playOnStart, setPlayOnStart] = useState(autoStart);
  const parent = status?.actor?.role === 'parent';

  useEffect(() => {
    let active = true;
    const actor = status?.actor;
    if (!actor) return;
    (actor.role === 'parent' ? listProfiles() : getProfile(actor.student_id!).then(p => [p])).then(p => {
      if (active) { setProfiles(p); setStudent(p[0]?.id ?? ''); }
    }, e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [status]);

  useEffect(() => {
    let active = true;
    if (!student) return;
    getSchoolRoutine(student).then(r => { if (active) { setRoutine(r.routine); setStartTime(r.routine?.start_time ?? ''); } }, e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [student]);

  useEffect(() => {
    if (!student) return;
    let active = true; let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { const r = await getTimetables(student); if (active) { setSchedule(chooseDay(r.timetables)); setRoutine(r.routine); setPollError(''); setLoaded(true); } }
      catch (e) { if (active) setPollError((e as Error).message); }
      if (active) timer = setTimeout(poll, 1000);
    };
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [student]);

  const slot = schedule?.slots.find(s => s.id === schedule.current_slot_id);
  const timetableId = schedule?.id; const currentSlotId = slot?.id; const isStarted = slot?.class_phase === 'started';
  useEffect(() => {
    if (!timetableId || !currentSlotId || !isStarted || parent) return;
    const timer = setInterval(() => { void deliveryAction({ timetableId, slotId: currentSlotId }, 'heartbeat').catch(() => undefined); }, 15000);
    return () => clearInterval(timer);
  }, [timetableId, currentSlotId, isStarted, parent]);
  useEffect(() => { if (autoStart && isStarted) router.replace('/timetable'); }, [autoStart, isStarted, router]);
  async function action(kind: string, rethrow = false) {
    if (!schedule || !slot) return;
    setBusy(true); setError('');
    try { if (kind === 'start' || kind === 'rejoin') setPlayOnStart(true); setSchedule(await deliveryAction({ timetableId: schedule.id, slotId: slot.id }, kind)); }
    catch (e) { setError((e as Error).message); if (rethrow) throw e; }
    finally { setBusy(false); }
  }
  async function saveTime(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError('');
    try { const result = await saveSchoolStartTime(student, startTime); setRoutine(result.routine); if (result.timetable) setSchedule(result.timetable); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  if (authError) return <div className="stack"><p className="error">The local application backend is unavailable.</p><button className="btn" onClick={() => void refresh()}>Try again</button></div>;
  if (!status) return <p>Loading your timetable…</p>;
  if (!status.setup_complete) return <div className="stack"><h1>Set up your household</h1><p>Create your parent PIN and child profile to set a daily school start time.</p><Link className="btn btn-primary" href="/setup">Set up Edaptive</Link></div>;
  if (!status.actor) return <div className="stack"><h1>Your timetable</h1><p>Select a child profile or unlock the parent area.</p><Link className="btn btn-primary" href="/">Choose a profile</Link><Link className="btn" href="/parent">Parent area</Link></div>;

  if (!parent && slot?.class_phase === 'started') return <div className="stack">
    <LessonPlayer key={slot.id} delivery={{ timetableId: schedule!.id, slotId: slot.id }} autoStart={playOnStart} onLeave={async () => { await action('exit', true); }} onFinished={() => void action('finish')} />
    {(error || pollError) && <p className="error" role="alert">{error || pollError}</p>}
  </div>;

  if (!parent) return <ChildClass loaded={loaded} schedule={schedule} slot={slot} busy={busy} error={error || pollError} onJoin={() => void action('start')} onSnooze={() => void action('borrow')} onRejoin={() => void action('rejoin')} />;

  const active = schedule?.status === 'active';
  const remaining = slot ? Math.max(0, Math.ceil((slot.start_ms - schedule!.server_now_ms) / 1000)) : 0;
  return <div className={`stack ${styles.demo}`}>
    <header className="row spread"><Link className="wordmark" href="/parent">Edaptive</Link><span className="eyebrow">Your learning day</span></header>
    <div><h1>A day of learning</h1><p>Maths lessons prepared for you, with time to think and take breaks.</p></div>
    {parent && <label className="field">Child profile<select className="input" value={student} onChange={e => { setStudent(e.target.value); setRoutine(null); setStartTime(''); setSchedule(null); }}>{profiles.map(p => <option key={p.id} value={p.id}>{p.display_name} · Grade {p.grade}</option>)}</select></label>}
    {!profiles.length && <p>Add a child profile in the <Link href="/parent">parent area</Link>.</p>}
    {parent && student && <form className="card stack" onSubmit={saveTime}>
      <h2>Daily school start time</h2>
      <label className="field">What time suits your child? · Pakistan time<input className="input" type="time" required value={startTime} onChange={e => setStartTime(e.target.value)} /></label>
      <p>This time applies each day. The system chooses the lessons and organises preparation, class length and breaks.</p>
      <button className="btn btn-primary" disabled={busy || !startTime}>{busy ? 'Saving…' : 'Save start time'}</button>
    </form>}
    {routine && <p className="notice" role="status">School starts at {routine.start_time} each day. {routine.message}</p>}
    {active && slot && <section className="card stack" aria-label="Lesson preparation">
      <div className="row spread"><h2>{slot.preparation?.status === 'ready' ? 'Lesson ready' : 'Preparing lesson'}</h2><strong className={styles.percent}>{slot.preparation?.percent ?? 0}%</strong></div>
      <progress max="100" value={slot.preparation?.percent ?? 0} aria-label="Lesson preparation progress" />
      <p className={needsMemoryHelp(slot.preparation) ? "notice" : undefined} role={needsMemoryHelp(slot.preparation) ? "alert" : "status"}>{preparationMessage(slot.preparation)}{!needsMemoryHelp(slot.preparation) && slot.preparation?.total ? ` · ${slot.preparation.completed} of ${slot.preparation.total} script sections` : ''}</p>
      <p>Class time: <strong>{timeText(slot.start_ms)}</strong> · {Math.floor(remaining / 60)}m {remaining % 60}s remaining</p>
      <p>Planned duration: {slot.timing?.minutes} minutes · three-minute buffer · {slot.timing?.basis === 'prepared_script' ? 'reviewed from the prepared script' : 'initial estimate from the cards'}</p>
      {!!slot.borrowed_minutes && <p>You snoozed for {slot.borrowed_minutes} minutes. Later lessons and breaks moved too.</p>}
    </section>}
    {schedule && <DayPlan timetable={schedule} />}
    {schedule?.status === 'completed' && <p className="notice">You’ve finished your planned Maths lessons.</p>}

    {(error || pollError) && <p className="error" role="alert">{error || pollError}</p>}
  </div>;
}
