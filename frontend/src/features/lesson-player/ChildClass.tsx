"use client";

import Link from 'next/link';
import type { PreparedSlot, SavedTimetable, LearningProgress, MathsModulesByGrade } from '@/lib/lesson-delivery-api';
import { needsMemoryHelp, preparationPercent } from './preparation-message';
import { ModuleRoadmap } from './ModuleRoadmap';
import { Pip } from '@/features/theme';
import styles from './timetable.module.css';

const clock = (ms: number) =>
  new Intl.DateTimeFormat('en-PK', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' }).format(ms);

function MathsMark() {
  return <svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <path d="M7 4v6M4 7h6" /><path d="M14 7h6" /><path d="M4.5 15.5l5 5M9.5 15.5l-5 5" /><path d="M14 16h6M14 20h6" />
  </svg>;
}

type Props = {
  grade?: number;
  mathsModules: MathsModulesByGrade;
  progress: LearningProgress | null;
  loaded: boolean;
  schedule: SavedTimetable | null;
  slot: PreparedSlot | undefined;
  busy: boolean;
  error: string;
  onJoin: () => void;
  onSnooze: () => void;
  onRejoin: () => void;
};

/** A calm class card followed by the child's grade-specific curriculum path. */
export function ChildClass({ grade, mathsModules, progress, loaded, schedule, slot, busy, error, onJoin, onSnooze, onRejoin }: Props) {
  const ready = slot?.preparation?.status === 'ready';
  const percent = preparationPercent(slot?.preparation);
  const dead = slot?.preparation?.status === 'cancelled' || slot?.preparation?.status === 'failed';
  const snoozed = (slot?.borrowed_minutes ?? 0) > 0;
  const active = schedule?.status === 'active';
  const memory = needsMemoryHelp(slot?.preparation);
  const stuck = !memory && slot?.preparation?.status === 'failed';
  const trouble = (memory || stuck) && slot?.preparation?.status !== 'ready'
    ? <p className="notice" role="alert">{memory
      ? 'Your teacher needs a little more room to get ready. Please ask a grown-up to close other tabs and apps.'
      : 'Your lesson needs a check before we start. Please ask a grown-up for help.'}</p>
    : null;

  let body: React.ReactNode = null;
  if (!loaded) {
    body = error ? null : <p role="status">Getting your day ready…</p>;
  } else if (schedule?.status === 'completed') {
    body = <p className={styles.childNote} role="status">{schedule.slots.some(s => s.kind === 'lesson' && s.class_phase === 'unfinished') ? 'Maths class has finished for today. Your next lesson is on the next school day.' : 'You’ve finished your Maths lesson.'}</p>;
  } else if (!active) {
    body = <p className={styles.childNote}>Your parent can set your daily school start time in the parent area.</p>;
  } else if (!slot) {
    body = <p className={styles.childNote} role="status">Your Maths lesson isn’t ready yet.</p>;
  } else if (slot.class_phase === 'exited') {
    body = <section className={`card ${styles.classCard} ui-class-card`} role="status" aria-label="Maths class">
      <div className={`${styles.classArt} ui-class-art`}><MathsMark /></div>
      <Pip className="ui-class-pip" size={120} waving />
      <h2 className={styles.classTitle}>You left Maths class</h2>
      <p className={styles.classLine}>You can come back until {clock(slot.end_ms)}. Your place is saved.</p>
      <div className={styles.classActions}>
        <button className={`btn btn-primary ${styles.big}`} disabled={busy} onClick={onRejoin}>Rejoin class</button>
      </div>
    </section>;
  } else if (slot.class_phase === 'unfinished') {
    body = <section className={`card ${styles.classCard} ui-class-card`} role="status" aria-label="Maths class">
      <div className={`${styles.classArt} ui-class-art`}><MathsMark /></div>
      <Pip className="ui-class-pip" size={120} waving />
      <h2 className={styles.classTitle}>Maths class has finished for today</h2>
      <p className={styles.classLine}>Tomorrow you’ll start your next Maths lesson.</p>
    </section>;
  } else if (slot.class_phase === 'ringing') {
    body = <section className={`card ${styles.classCard} ui-class-card`} role="alert" aria-label="Maths class">
      <div className={`${styles.classArt} ui-class-art`}><MathsMark /></div>
      <Pip className="ui-class-pip" size={120} waving />
      <h2 className={styles.classTitle}>It’s time for Maths!</h2>
      <p className={styles.classLine}>{ready ? 'Your lesson is ready.' : 'Your teacher is almost ready.'}</p>
      {trouble}
      {!ready && !dead && <label className={styles.classProgress}>
        <progress max="100" value={percent} aria-label="Getting the lesson ready" />
        <span>{percent}%</span>
      </label>}
      <div className={styles.classActions}>
        <button className={`btn btn-primary ${styles.big}`} disabled={busy || !ready} onClick={onJoin}>Join class</button>
        {!snoozed && <button className={`btn ${styles.big}`} disabled={busy} onClick={onSnooze}>Snooze 5 minutes</button>}
      </div>
    </section>;
  } else {
    body = <section className={`card ${styles.classCard} ui-class-card`} role="status" aria-label="Maths class">
      <div className={`${styles.classArt} ui-class-art`}><MathsMark /></div>
      <Pip className="ui-class-pip" size={120} waving />
      <h2 className={styles.classTitle}>Maths starts at {clock(slot.start_ms)}</h2>
      {ready && <p className={styles.classLine} role="status">Your lesson is ready.</p>}
      {!ready && slot.delay_notice && <p className={styles.classLine} role="status">{slot.delay_notice}</p>}
      {trouble}
    </section>;
  }

  return <div className={`stack ${styles.child} ui-child`}>
    <header className="row spread">
      <Link className="wordmark" href="/home">Edaptive</Link>
      <Link className="btn" href="/home">Home</Link>
    </header>
    <h1>A day of learning</h1>
    {body}
    {grade && <ModuleRoadmap grade={grade} modules={mathsModules[grade] ?? []} progress={progress} currentModule={slot?.module} />}
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}
