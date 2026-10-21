"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { getAuthStatus } from '@/lib/api';
import { getLessonAlarmSetting, getTimetables } from '@/lib/lesson-delivery-api';
import { lessonAlarm } from '@/features/voice';

/**
 * Class time is noticed on every page. Parent permission controls whether the chime plays;
 * the child's first tap unlocks browser audio, with an explicit retry if that tap was missed.
 */
export function ScheduledAlarm() {
  const pathname = usePathname();
  const [student, setStudent] = useState(false);
  const [due, setDue] = useState(false);
  const [sound, setSound] = useState(false);
  const [audioReady, setAudioReady] = useState(false);
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
          const alarm = await getLessonAlarmSetting(id).catch(() => ({ granted: false }));
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
    if (!student) return;
    let active = true;
    const unlock = () => { void lessonAlarm().unlock().then(ready => { if (active) setAudioReady(ready); }); };
    window.addEventListener('pointerdown', unlock);
    window.addEventListener('keydown', unlock);
    return () => { active = false; window.removeEventListener('pointerdown', unlock); window.removeEventListener('keydown', unlock); };
  }, [student]);
  useEffect(() => {
    let active = true;
    let ready = false;
    if (due && sound) ready = lessonAlarm().ring();
    else lessonAlarm().stop();
    queueMicrotask(() => { if (active) setAudioReady(ready); });
    return () => { active = false; lessonAlarm().stop(); };
  }, [due, sound]);
  const needsTap = student && due && sound && !audioReady;
  // On the Maths screen the class card already says it is time; a second notice there is noise.
  if (!student || !due || (pathname.startsWith('/timetable') && !needsTap)) return null;
  return <aside className="page" aria-label="Scheduled class notification">
    <div className="card row spread" role="alert">
      <p>{needsTap ? 'Tap to hear your class chime.' : 'It’s time for your Maths class.'}</p>
      {needsTap && <button className="btn" onClick={() => { void lessonAlarm().unlock().then(setAudioReady); }}>Enable sound</button>}
      {!pathname.startsWith('/timetable') && <Link className="btn btn-primary" href="/timetable">Open class</Link>}
    </div>
  </aside>;
}
