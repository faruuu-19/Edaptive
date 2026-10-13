"use client";

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { getAuthStatus } from '@/lib/api';
import { getTimetables } from '@/lib/lesson-delivery-api';
import { LocalAlarm } from '@/features/voice';

/** Mounted across the app: class time is noticed on Home as well as Timetable. */
export function ScheduledAlarm() {
  const [student, setStudent] = useState(false);
  const [due, setDue] = useState(false);
  const [armed, setArmed] = useState(false);
  const alarm = useRef<LocalAlarm | null>(null);
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const status = await getAuthStatus();
        if (!active) return;
        const id = status.actor?.role === 'student' ? status.actor.student_id : null;
        setStudent(!!id);
        if (id) {
          const result = await getTimetables(id);
          const timetable = result.timetables.find(t => t.status === 'active');
          const slot = timetable?.slots.find(s => s.id === timetable.current_slot_id);
          if (active) setDue(slot?.class_phase === 'ringing');
        } else setDue(false);
      } catch { if (active) setDue(false); }
      if (active) timer = setTimeout(poll, 1500);
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, []);
  useEffect(() => { if (due && armed) alarm.current?.ring(); else alarm.current?.stop(); }, [due, armed]);
  useEffect(() => () => alarm.current?.close(), []);
  if (!student || (armed && !due)) return null;
  return <aside className="page" aria-label="Scheduled class notification">
    <div className="card row spread" role={due ? 'alert' : 'status'}>
      <p>{due ? 'It’s time for your Maths class.' : 'Enable the lesson alarm for this device.'}</p>
      {!armed && <button className="btn" onClick={() => { alarm.current ??= new LocalAlarm(); void alarm.current.unlock().then(() => setArmed(true)); }}>Enable lesson alarm</button>}
      {due && <Link className="btn btn-primary" href="/timetable">Open class</Link>}
    </div>
  </aside>;
}
