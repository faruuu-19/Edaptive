"use client";

import { useEffect, useState } from 'react';
import { getAttendance, type Attendance, type AttendanceRecord } from '@/lib/parent-api';
import styles from './parent.module.css';

const SUBJECTS: Record<string, string> = { math: 'Maths', english: 'English', science: 'Science' };
const day = (isoDate: string) =>
  new Intl.DateTimeFormat('en-PK', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(`${isoDate}T00:00:00Z`));

export function describeAttendance(record: AttendanceRecord): string {
  switch (record.reason) {
    case 'completed': return 'Finished the lesson.';
    case 'left_after_threshold': return `Left after staying for ${record.attended_percent}% of the lesson.`;
    case 'left_early': return `Left early, after ${record.attended_percent}% of the lesson.`;
    default: return 'Did not join.';
  }
}

/** Every class's attendance for one child: present means staying for at least 70% of the lesson. */
export function AttendanceLog({ studentId, name }: { studentId: string; name: string }) {
  const [log, setLog] = useState<Attendance | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { const result = await getAttendance(studentId); if (active) { setLog(result); setError(false); } }
      catch { if (active) setError(true); }
      if (active) timer = setTimeout(poll, 10000);
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [studentId]);
  if (!log) return <section className="card" aria-label="Attendance"><p role="status" className="muted">{error ? 'Attendance is unavailable right now.' : 'Loading attendance…'}</p></section>;
  return <section className="card stack" aria-labelledby="attendance-title">
    <div className="row spread"><h2 id="attendance-title">Attendance</h2>
      <span className={styles.attendanceTotals}><strong>{log.summary.present}</strong> present · <strong>{log.summary.absent}</strong> absent</span></div>
    <p className="muted">{name} is marked present for a lesson after staying for at least {log.threshold_percent}% of it.</p>
    {log.records.length === 0
      ? <p role="status">No classes have been recorded yet.</p>
      : <ul className={styles.attendanceList}>{log.records.map(record => <li key={`${record.school_date}-${record.concept_id}-${record.recorded_at}`}>
        <div><strong>{day(record.school_date)}</strong><span>{SUBJECTS[record.subject] ?? 'Lesson'} · {record.lesson_title || 'Lesson'}</span></div>
        <div className={styles.attendanceDetail}>
          <span className={record.status === 'present' ? styles.present : styles.absent}>{record.status === 'present' ? 'Present' : 'Absent'}</span>
          <small>{describeAttendance(record)}</small>
        </div>
      </li>)}</ul>}
    {log.summary.absent > 0 && <p className="notice">Parts of a lesson {name} missed will be available to watch later in the recorded lectures library (coming soon).</p>}
  </section>;
}
