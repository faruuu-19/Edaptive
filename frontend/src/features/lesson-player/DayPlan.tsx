"use client";
import type { SavedTimetable } from '@/lib/lesson-delivery-api';
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
