"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { getAuthStatus } from '@/lib/api';
import { getLessonAlarmSetting, getTimetables } from '@/lib/lesson-delivery-api';
import { lessonAlarm } from '@/features/voice';

/**
 * Class time is noticed on every page. The child has no alarm controls: whether the chime plays is a
 * parent permission, and the browser's sound unlock happens silently on the child's first tap.
 */
export function ScheduledAlarm() {
  const pathname = usePathname();
  const [student, setStudent] = useState(false);
  const [due, setDue] = useState(false);
  const [sound, setSound] = useState(false);
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const status = await getAuthStatus();
        if (!active) return;
        const id = status.actor?.role === 'student' ? status.actor.student_id : null;
        setStudent(!!id);
        if (id) {
          const [result, alarm] = await Promise.all([getTimetables(id), getLessonAlarmSetting(id)]);
          const timetable = result.timetables.find(t => t.status === 'active');
          const slot = timetable?.slots.find(s => s.id === timetable.current_slot_id);
          if (active) { setDue(slot?.class_phase === 'ringing'); setSound(alarm.granted); }
        } else { setDue(false); setSound(false); }
      } catch { if (active) setDue(false); }
      if (active) timer = setTimeout(poll, 1500);
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, []);
  useEffect(() => {
    if (!sound) return;
    const unlock = () => void lessonAlarm().unlock();
    window.addEventListener('pointerdown', unlock, { once: true });
    window.addEventListener('keydown', unlock, { once: true });
    return () => { window.removeEventListener('pointerdown', unlock); window.removeEventListener('keydown', unlock); };
  }, [sound]);
  useEffect(() => {
    if (due && sound) lessonAlarm().ring(); else lessonAlarm().stop();
    return () => lessonAlarm().stop();
  }, [due, sound]);
  // On the Maths screen the class card already says it is time; a second notice there is noise.
  if (!student || !due || pathname.startsWith('/timetable')) return null;
  return <aside className="page" aria-label="Scheduled class notification">
    <div className="card row spread" role="alert">
      <p>It’s time for your Maths class.</p>
      <Link className="btn btn-primary" href="/timetable">Open class</Link>
    </div>
  </aside>;
}
