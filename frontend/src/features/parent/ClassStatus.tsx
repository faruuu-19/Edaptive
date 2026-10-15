"use client";

import { useEffect, useState } from 'react';
import { isWaitingToPrepare, needsMemoryHelp, prepareTimeText } from '@/features/lesson-player';
import { getTimetables, type SavedTimetable } from '@/lib/lesson-delivery-api';
import styles from './parent.module.css';

const clock = (ms: number) =>
  new Intl.DateTimeFormat('en-PK', { timeZone: 'Asia/Karachi', hour: '2-digit', minute: '2-digit' }).format(ms);

export type ClassSummary = { headline: string; detail: string; attention: boolean };

/** What a parent should know about today's class, in plain words. */
export function describeClass(name: string, day: SavedTimetable | undefined): ClassSummary {
  const slot = day?.slots.find(s => s.id === day.current_slot_id) ?? day?.slots.find(s => s.kind === 'lesson');
  if (!day || !slot || slot.kind !== 'lesson') return { headline: 'No class is scheduled yet', detail: 'Set a daily start time below.', attention: false };
  const prep = slot.preparation;
  const waiting = slot.class_phase === 'waiting' || slot.class_phase === 'ringing';
  if (waiting && prep && prep.status !== 'ready') {
    if (needsMemoryHelp(prep)) {
      return { headline: `${name}’s Maths lesson is paused`, detail: 'This computer is low on memory. Please close other browser tabs and apps; the lesson will carry on preparing by itself.', attention: true };
    }
    if (prep.status === 'failed') {
      return { headline: `${name}’s Maths lesson could not be prepared`, detail: 'Edaptive will try again automatically. If this stays, restart Edaptive.', attention: true };
    }
    if (/unavailable/i.test(prep.message ?? '')) {
      return { headline: 'The lesson teacher is not responding', detail: 'Edaptive will keep trying. If this stays, restart Edaptive.', attention: true };
    }
  }
  const part = `part ${(slot.position ?? 0) + 1}${slot.segment_count ? ` of ${slot.segment_count}` : ''}`;
  switch (slot.class_phase) {
    case 'completed':
      return { headline: 'Maths finished', detail: `${name} completed today’s Maths lesson.`, attention: false };
    case 'started':
      return { headline: `${name} is in class now`, detail: `Currently at ${part}.`, attention: false };
    case 'ringing':
      return { headline: 'Class time has started', detail: `Waiting for ${name} to join Maths.`, attention: false };
    case 'exited':
      return {
        headline: `${name} left the class`,
        detail: `${slot.exit_reason === 'timeout' ? 'The connection was lost' : `${name} chose to leave`} at ${clock(slot.exited_at_ms ?? slot.end_ms)}, at ${part}. They can rejoin until ${clock(slot.end_ms)}.`,
        attention: true,
      };
    case 'left_early':
      return {
        headline: `${name} left class early`,
        detail: `They left at ${clock(slot.exited_at_ms ?? slot.end_ms)}, at ${part}. Maths will continue on the next school day from where they stopped. Other classes keep their times.`,
        attention: true,
      };
    default:
      return {
        headline: `Maths starts at ${clock(slot.start_ms)}`,
        detail: isWaitingToPrepare(slot.preparation) ? `The lesson will be prepared ${prepareTimeText(slot.prepare_at_ms, day.server_now_ms)}. Nothing for you to do.` : 'Nothing for you to do.',
        attention: false,
      };
  }
}

export function ClassStatus({ studentId, name }: { studentId: string; name: string }) {
  const [day, setDay] = useState<SavedTimetable | undefined | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const result = await getTimetables(studentId);
        if (active) { setDay(result.timetables.find(t => t.status === 'active') ?? result.timetables[0]); setUnavailable(false); }
      } catch { if (active) setUnavailable(true); }
      if (active) timer = setTimeout(poll, 4000);
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [studentId]);
  if (day === null) return <section className="card" aria-label="Today’s class"><p role="status" className="muted">{unavailable ? 'Class status is unavailable right now.' : 'Checking today’s class…'}</p></section>;
  const summary = describeClass(name, day);
  return <section className={`card stack ${summary.attention ? styles.classAttention : ''}`} aria-labelledby="class-status-title">
    <div className="row spread"><h2 id="class-status-title">Today’s class</h2>{summary.attention && <span className={styles.permissionStatus}>Needs your attention</span>}</div>
    <p role="status"><strong>{summary.headline}</strong></p>
    <p className="muted">{summary.detail}</p>
  </section>;
}
