"use client";

import { useEffect, useState } from 'react';
import { getTimetables, type SavedTimetable } from '@/lib/lesson-delivery-api';
import { DayPlan, chooseDay } from './DayPlan';

/** The child's timetable on the home screen: what and when. Preparation and the class card live elsewhere. */
export function TodaysTimetable({ studentId }: { studentId: string }) {
  const [day, setDay] = useState<SavedTimetable | null>(null);
  const [note, setNote] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const result = await getTimetables(studentId);
        if (active) { setDay(chooseDay(result.timetables)); setNote(result.routine?.message ?? 'Your parent can set your daily school start time.'); setLoaded(true); setError(''); }
      } catch { if (active) setError('Your timetable is temporarily unavailable. Trying again…'); }
      if (active) timer = setTimeout(poll, 1000);
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [studentId]);
  return <div className="stack" style={{ gap: 24 }}>
    {error && <p className="error" role="alert">{error}</p>}
    {!loaded && !error && <p role="status">Loading your school day…</p>}
    {loaded && !day && <section className="card stack"><h2>Your school day</h2><p>{note}</p></section>}
    {day && <DayPlan timetable={day} simple />}
  </div>;
}
