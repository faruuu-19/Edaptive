"use client";

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { useAuthStatus } from '@/features/auth';
import { LocalAlarm } from '@/features/voice';
import { getProfile, listProfiles, type Profile } from '@/lib/api';
import { deliveryAction, getDeliveryCatalog, getTimetables, planTimetable, type DeliveryCard, type SavedTimetable } from '@/lib/lesson-delivery-api';
import { LessonPlayer } from './LessonPlayer';
import styles from './timetable.module.css';

const timeText = (ms: number) => new Intl.DateTimeFormat('en-PK', { timeZone: 'Asia/Karachi', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(ms);
const localInput = (ms: number) => new Date(ms + 5 * 3600000).toISOString().slice(0, 19);

export function Timetable() {
  const { status, error: authError, refresh } = useAuthStatus();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [student, setStudent] = useState('');
  const [cards, setCards] = useState<DeliveryCard[]>([]);
  const [concepts, setConcepts] = useState<string[]>([]);
  const [schedule, setSchedule] = useState<SavedTimetable | null>(null);
  const [start, setStart] = useState('');
  const [breakMinutes, setBreakMinutes] = useState(5);
  const [lead, setLead] = useState(30);
  const [autoLead, setAutoLead] = useState(true);
  const [allowDrafts, setAllowDrafts] = useState(false);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [busy, setBusy] = useState(false);
  const [armed, setArmed] = useState(false);
  const [playOnStart, setPlayOnStart] = useState(false);
  const alarm = useRef<LocalAlarm | null>(null);
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
    getDeliveryCatalog(student).then(r => { if (active) setCards(r.cards); }, e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [student]);

  useEffect(() => {
    if (!student) return;
    let active = true; let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { const r = await getTimetables(student); if (active) { setSchedule(r.timetables.find(t => t.status === 'active') ?? r.timetables[0] ?? null); setPollError(''); } }
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
  useEffect(() => {
    alarm.current?.stop();
  }, [slot?.class_phase, armed, parent]);
  useEffect(() => () => alarm.current?.close(), []);

  async function arm() { alarm.current ??= new LocalAlarm(); await alarm.current.unlock(); setArmed(true); }
  async function action(kind: string) {
    if (!schedule || !slot) return;
    setBusy(true); setError('');
    try { if (kind === 'start') { await arm(); setPlayOnStart(true); } setSchedule(await deliveryAction({ timetableId: schedule.id, slotId: slot.id }, kind)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function create(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError('');
    try { setSchedule(await planTimetable({ student_id: student, starts_at: `${start}+05:00`, concept_ids: concepts, break_minutes: breakMinutes, prepare_minutes: autoLead ? null : lead, allow_drafts: allowDrafts })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  if (authError) return <div className="stack"><p className="error">The local application backend is unavailable.</p><button className="btn" onClick={() => void refresh()}>Try again</button></div>;
  if (!status) return <p>Loading your timetable…</p>;
  if (!status.setup_complete) return <div className="stack"><h1>Set up your household</h1><p>Create your parent PIN and child profile before scheduling lessons.</p><Link className="btn btn-primary" href="/setup">Set up Edaptive</Link></div>;
  if (!status.actor) return <div className="stack"><h1>Your timetable</h1><p>Select a child profile or unlock the parent area.</p><Link className="btn btn-primary" href="/">Choose a profile</Link><Link className="btn" href="/parent">Parent area</Link></div>;

  if (slot?.class_phase === 'started') return <div className="stack">
    <div className="row spread"><Link className="wordmark" href="/home">Edaptive</Link><button className="btn" disabled={busy} onClick={() => void action('cancel')}>Exit class</button></div>
    <LessonPlayer key={slot.id} delivery={{ timetableId: schedule!.id, slotId: slot.id }} autoStart={playOnStart} onFinished={() => void action('finish')} />
    {(error || pollError) && <p className="error" role="alert">{error || pollError}</p>}
  </div>;

  const active = schedule?.status === 'active';
  const remaining = slot ? Math.max(0, Math.ceil((slot.start_ms - schedule!.server_now_ms) / 1000)) : 0;
  return <div className={`stack ${styles.demo}`}>
    <header className="row spread"><Link className="wordmark" href={parent ? '/parent' : '/home'}>Edaptive</Link><span className="eyebrow">Your learning day</span></header>
    <div><h1>A day of learning</h1><p>Maths lessons prepared for you, with time to think and take breaks.</p></div>
    {parent && <label className="field">Child profile<select className="input" value={student} onChange={e => { setStudent(e.target.value); setCards([]); setConcepts([]); setSchedule(null); }}>{profiles.map(p => <option key={p.id} value={p.id}>{p.display_name} · Grade {p.grade}</option>)}</select></label>}
    {!profiles.length && <p>Add a child profile in the <Link href="/parent">parent area</Link>.</p>}
    {parent && !active && student && <form className="card stack" onSubmit={create}>
      <h2>Plan Maths lessons</h2>
      <label className="field">First class time · Pakistan time<input className="input" type="datetime-local" step="1" required value={start} onChange={e => setStart(e.target.value)} /></label>
      <button className="btn" type="button" onClick={() => setStart(localInput(Date.now() + Math.max(35, (cards.find(c => c.id === concepts[0])?.recommended_prepare_minutes ?? 30) + 5) * 60000))}>Choose a time with preparation headroom</button>
      <label className="field">Lessons<select className="input" multiple value={concepts} onChange={e => setConcepts(Array.from(e.target.selectedOptions, o => o.value))}>{cards.map(c => <option key={c.id} value={c.id}>Module {c.module} · {c.title}</option>)}</select></label>
      <p>Leave the lesson selection empty to let the agent choose the next available lesson. Duration is reviewed from the script: 15–35 minutes, including a three-minute buffer.</p>
      <label className="field">Break between classes · minutes<input className="input" type="number" min="1" max="60" value={breakMinutes} onChange={e => setBreakMinutes(Number(e.target.value))} /></label>
      <label className="row"><input type="checkbox" checked={autoLead} onChange={e => setAutoLead(e.target.checked)} />Let the agent estimate preparation lead time</label>
      {!autoLead && <label className="field">Start preparation this many minutes before class<input className="input" type="number" min="1" max="120" value={lead} onChange={e => setLead(Number(e.target.value))} /></label>}
      <label className="row"><input type="checkbox" checked={allowDrafts} onChange={e => setAllowDrafts(e.target.checked)} />Allow draft cards for local evaluation</label>
      <button className="btn btn-primary" disabled={busy || !cards.length}>Create timetable</button>
    </form>}
    {active && slot && <section className="card stack" aria-label="Lesson preparation">
      <div className="row spread"><h2>{slot.preparation?.status === 'ready' ? 'Lesson ready' : 'Preparing lesson'}</h2><strong className={styles.percent}>{slot.preparation?.percent ?? 0}%</strong></div>
      <progress max="100" value={slot.preparation?.percent ?? 0} aria-label="Lesson preparation progress" />
      <p role="status">{slot.preparation?.message}{slot.preparation?.total ? ` · ${slot.preparation.completed} of ${slot.preparation.total} script sections` : ''}</p>
      <p>Class time: <strong>{timeText(slot.start_ms)}</strong> · {Math.floor(remaining / 60)}m {remaining % 60}s remaining</p>
      <p>Planned duration: {slot.timing?.minutes} minutes · three-minute buffer · {slot.timing?.basis === 'prepared_script' ? 'reviewed from the prepared script' : 'initial estimate from the cards'}</p>
      {!!slot.borrowed_minutes && <p>You borrowed {slot.borrowed_minutes} minutes. Later lessons and breaks moved too.</p>}

      {parent && slot.preparation?.status === 'failed' && <button className="btn" disabled={busy} onClick={() => void action('retry')}>Retry preparation</button>}
      {parent && <button className="btn btn-quiet" disabled={busy} onClick={() => void action('cancel')}>Cancel timetable</button>}
    </section>}
    {!parent && slot?.class_phase === 'ringing' && <section className={`card stack ${styles.alarm}`} role="alert">
      <h2>It’s time for Maths!</h2><p>{slot.preparation?.status === 'ready' ? 'Your lesson is ready.' : 'Your teacher is still preparing. You can borrow five minutes.'}</p>
      <div className="row"><button className="btn btn-primary" disabled={busy || slot.preparation?.status !== 'ready'} onClick={() => void action('start')}>Start class</button><button className="btn" disabled={busy} onClick={() => void action('borrow')}>Borrow 5 minutes</button></div>
    </section>}
    {schedule && <section className="stack"><h2>Your timetable</h2><ol className={styles.slots}>{schedule.slots.map(s => <li key={s.id} className={`${styles.slot} ${s.kind === 'break' ? styles.breakSlot : ''}`}><strong>{s.title}</strong><span>{timeText(s.start_ms)} – {timeText(s.end_ms)}</span><small>{s.kind === 'lesson' ? s.class_phase : 'Time to take a break'}</small></li>)}</ol></section>}
    {schedule?.status === 'completed' && <p className="notice">You’ve finished your planned Maths lessons.</p>}
    <section className="row"><div className="card"><h2>Science</h2><p>Coming soon</p></div><div className="card"><h2>English</h2><p>Coming soon</p></div></section>
    {(error || pollError) && <p className="error" role="alert">{error || pollError}</p>}
  </div>;
}
