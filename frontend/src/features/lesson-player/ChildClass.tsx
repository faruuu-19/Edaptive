"use client";

import Link from 'next/link';
import type { PreparedSlot, SavedTimetable } from '@/lib/lesson-delivery-api';
import { needsMemoryHelp } from './preparation-message';
import styles from './timetable.module.css';

const clock = (ms: number) =>
  new Intl.DateTimeFormat('en-PK', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' }).format(ms);

function MathsMark() {
  return <svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <path d="M7 4v6M4 7h6" /><path d="M14 7h6" /><path d="M4.5 15.5l5 5M9.5 15.5l-5 5" /><path d="M14 16h6M14 20h6" />
  </svg>;
}

type Props = {
  loaded: boolean;
  schedule: SavedTimetable | null;
  slot: PreparedSlot | undefined;
  busy: boolean;
  error: string;
  onJoin: () => void;
  onSnooze: () => void;
  onRejoin: () => void;
};

/** What a child sees after tapping Maths: one calm card, no timetable and no planning detail. */
export function ChildClass({ loaded, schedule, slot, busy, error, onJoin, onSnooze, onRejoin }: Props) {
  const ready = slot?.preparation?.status === 'ready';
  const percent = ready ? 100 : Math.round(slot?.preparation?.percent ?? 0);
  const dead = slot?.preparation?.status === 'cancelled' || slot?.preparation?.status === 'failed';
  const snoozed = (slot?.borrowed_minutes ?? 0) > 0;
  const active = schedule?.status === 'active';
  const memory = needsMemoryHelp(slot?.preparation);
  const stuck = !memory && slot?.preparation?.status === 'failed';
  const trouble = (memory || stuck) && slot?.preparation?.status !== 'ready'
    ? <p className="notice" role="alert">{memory
      ? 'Your teacher needs a little more room to get ready. Please ask a grown-up to close other tabs and apps.'
      : 'Your teacher is having trouble getting ready. A grown-up has been told.'}</p>
    : null;

  let body: React.ReactNode = null;
  if (!loaded) {
    body = error ? null : <p role="status">Getting your day ready…</p>;
  } else if (schedule?.status === 'completed') {
    body = <p className={styles.childNote} role="status">You’ve finished your Maths lesson.</p>;
  } else if (!active) {
    body = <p className={styles.childNote}>Your parent can set your daily school start time in the parent area.</p>;
  } else if (!slot) {
    body = <p className={styles.childNote} role="status">Your Maths lesson isn’t ready yet.</p>;
  } else if (slot.class_phase === 'exited') {
    body = <section className={`card ${styles.classCard}`} role="status" aria-label="Maths class">
      <div className={styles.classArt}><MathsMark /></div>
      <h2 className={styles.classTitle}>You left Maths class</h2>
      <p className={styles.classLine}>You can come back until {clock(slot.end_ms)}. Your place is saved.</p>
      <div className={styles.classActions}>
        <button className={`btn btn-primary ${styles.big}`} disabled={busy} onClick={onRejoin}>Rejoin class</button>
      </div>
    </section>;
  } else if (slot.class_phase === 'left_early') {
    body = <section className={`card ${styles.classCard}`} role="status" aria-label="Maths class">
      <div className={styles.classArt}><MathsMark /></div>
      <h2 className={styles.classTitle}>Maths class has finished for today</h2>
      <p className={styles.classLine}>We’ll carry on from where you stopped on the next school day.</p>
    </section>;
  } else if (slot.class_phase === 'ringing') {
    body = <section className={`card ${styles.classCard}`} role="alert" aria-label="Maths class">
      <div className={styles.classArt}><MathsMark /></div>
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
    body = <section className={`card ${styles.classCard}`} role="status" aria-label="Maths class">
      <div className={styles.classArt}><MathsMark /></div>
      <h2 className={styles.classTitle}>Maths starts at {clock(slot.start_ms)}</h2>
      {trouble}
    </section>;
  }

  return <div className={`stack ${styles.child}`}>
    <header className="row spread">
      <Link className="wordmark" href="/home">Edaptive</Link>
      <Link className="btn" href="/home">Home</Link>
    </header>
    <h1>A day of learning</h1>
    {body}
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}
