"use client";

import { useEffect, useState } from 'react';
import { getTimetables } from '@/lib/lesson-delivery-api';
import { chooseDay } from './DayPlan';
import { isWaitingToPrepare, prepareTimeText } from './prepare-time';
import { needsMemoryHelp } from './preparation-message';
import styles from './timetable.module.css';

/** A small preparation bar with a percentage for the Maths tile on the child's home screen. */
export function PrepProgress({ studentId }: { studentId: string }) {
  const [percent, setPercent] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const [waitingText, setWaitingText] = useState<string | null>(null);
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const { timetables } = await getTimetables(studentId);
        const day = chooseDay(timetables);
        const slot = day?.status === 'active' ? day.slots.find(s => s.id === day.current_slot_id) : undefined;
        const value = slot ? (slot.preparation?.status === 'ready' ? 100 : Math.round(slot.preparation?.percent ?? 0)) : null;
        if (active) { setPercent(value === null ? null : Math.max(0, Math.min(100, value))); setPaused(!!slot && needsMemoryHelp(slot.preparation)); setWaitingText(slot && day && isWaitingToPrepare(slot.preparation) ? prepareTimeText(slot.prepare_at_ms, day.server_now_ms) : null); }
      } catch { if (active) setPercent(null); }
      if (active) timer = setTimeout(poll, 2000);
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [studentId]);
  if (percent === null) return null;
  if (waitingText) return <span className={styles.tileProgress}><span>Lesson prepares {waitingText}</span></span>;
  return <span className={styles.tileProgress}>
    <progress max="100" value={percent} aria-label="Maths lesson preparation" />
    <span>{paused ? 'Paused' : `${percent}%`}</span>
  </span>;
}
