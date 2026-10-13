"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { LocalAlarm } from "@/features/voice";
import { actOnDemoSchedule, createDemoSchedule, getCardChoices, getDemoSchedule, type CardChoice, type DemoSchedule, type ScheduleResponse } from "@/lib/timetable-preview-api";
import { LessonPlayer } from "./LessonPlayer";
import styles from "./timetable.module.css";

const DEMO_CARD = "math_g2_m1_l1_pairs_to_ten";
const timeText = (ms: number) => new Intl.DateTimeFormat("en-PK", { timeZone: "Asia/Karachi", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(ms);
const inputTime = (ms: number) => new Date(ms + 5 * 3600000).toISOString().slice(0, 19);

export function TimetableDemo() {
  const [cards, setCards] = useState<CardChoice[]>([]);
  const [concept, setConcept] = useState(DEMO_CARD);
  const [startTime, setStartTime] = useState("");
  const [lead, setLead] = useState(10);
  const [mode, setMode] = useState<"fresh" | "reuse">("fresh");
  const [schedule, setSchedule] = useState<DemoSchedule | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [soundArmed, setSoundArmed] = useState(false);
  const alarm = useRef<LocalAlarm | null>(null);
  const selected = cards.find(c => c.id === concept);

  useEffect(() => {
    const controller = new AbortController();
    getCardChoices(controller.signal).then(r => setCards(r.cards)).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { const r = await getDemoSchedule(controller.signal); setSchedule(r.schedule); }
      catch (e) { if (!controller.signal.aborted) setError((e as Error).message); }
      if (!controller.signal.aborted) timer = setTimeout(poll, 500);
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  useEffect(() => {
    if (schedule?.class_phase === "ringing" && soundArmed) alarm.current?.ring();
    else alarm.current?.stop();
  }, [schedule?.class_phase, soundArmed]);

  useEffect(() => () => alarm.current?.close(), []);

  function accept(result: ScheduleResponse) { setSchedule(result.schedule); setError(""); }

  async function arm() {
    alarm.current ??= new LocalAlarm(); await alarm.current.unlock(); setSoundArmed(true);
  }

  async function make(quick = false) {
    setBusy(true); setError("");
    try {
      await arm();
      const start = quick ? Date.now() + 30000 : new Date(`${startTime}+05:00`).getTime();
      accept(await createDemoSchedule(quick ? DEMO_CARD : concept, start, quick ? 30 : lead * 60, quick ? "reuse" : mode));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function act(action: "start" | "borrow" | "cancel" | "finish") {
    if (!schedule) return;
    setBusy(true); setError("");
    try { accept(await actOnDemoSchedule(schedule.id, action)); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  if (schedule?.class_phase === "started") return <div className="stack">
    <div className="row spread"><Link className="btn" href="/timetable-demo">Timetable demo</Link><button className="btn" onClick={() => void act("cancel")}>End demo class</button></div>
    <LessonPlayer key={schedule.id} scheduleId={schedule.id} autoStart onFinished={() => void act("finish")} />
    {error && <p className="error" role="alert">{error}</p>}
  </div>;

  const active = schedule && !["cancelled", "completed"].includes(schedule.class_phase);
  const remaining = schedule ? Math.max(0, Math.ceil((schedule.start_ms - schedule.server_now_ms) / 1000)) : 0;

  return <div className={`stack ${styles.demo}`}>
    <header className="row spread"><Link className="wordmark" href="/">Edaptive</Link><span className="eyebrow">Timetable demo · draft content</span></header>
    <div><h1>A day of learning</h1><p>Prepare ahead, take breaks, and begin when it’s class time.</p></div>
    {!active && <form className={`card stack ${styles.form}`} onSubmit={e => { e.preventDefault(); void make(); }}>
      <h2>Choose your demo class</h2>
      <label className="field">Maths lesson<select className="input" value={concept} onChange={e => { setConcept(e.target.value); setMode("fresh"); }}>
        {cards.map(c => <option key={c.id} value={c.id}>Grade {c.grade} · Module {c.module} · {c.title}</option>)}
      </select></label>
      <label className="field">Class time · Pakistan time<input className="input" type="datetime-local" step="1" value={startTime} required onChange={e => setStartTime(e.target.value)} /></label>
      <button type="button" className="btn" onClick={() => setStartTime(inputTime(Date.now() + 10 * 60000))}>Set time to 10 minutes from now</button>
      <label className="field">Start preparing this many minutes before class<input className="input" type="number" min="0" max="60" value={lead} onChange={e => setLead(Number(e.target.value))} /></label>
      <label className="field">Preparation<select className="input" value={mode} onChange={e => setMode(e.target.value as "fresh" | "reuse")}>
        <option value="fresh">Prepare a new script from the cards · local Qwen</option>
        {selected?.quick_demo_available && <option value="reuse">Recheck the existing script · quick demo</option>}
      </select></label>
      <div className="row"><button className="btn btn-primary" disabled={busy || !cards.length}>Create timetable &amp; enable alarm</button>
        <button type="button" className="btn" disabled={busy || !cards.length} onClick={() => void make(true)}>Quick demo · class in 30 seconds</button></div>
      <p className={styles.note}>Quick demo rechecks the existing Grade 2 script; it does not generate a new one. Fresh Qwen preparation needs several minutes. Keep this tab open for the alarm.</p>
    </form>}
    {active && <section className={`card stack ${styles.preparation}`} aria-label="Lesson preparation">
      <div className="row spread"><h2>{schedule.preparation === "ready" ? "Lesson ready" : "Preparing lesson"}</h2><strong className={styles.percent}>{schedule.percent}%</strong></div>
      <progress max="100" value={schedule.percent} aria-label="Lesson preparation progress" />
      <p role="status">{schedule.message}{schedule.total ? ` · ${schedule.completed} of ${schedule.total} script sections checked` : ""}</p>
      <p>Class time: <strong>{timeText(schedule.start_ms)}</strong> · {Math.floor(remaining / 60)}m {remaining % 60}s remaining</p>
      {schedule.borrowed_minutes > 0 && <p>You borrowed {schedule.borrowed_minutes} minutes. The later classes moved too.</p>}
      {!soundArmed && <button className="btn" onClick={() => void arm()}>Enable class alarm</button>}
      <button className="btn btn-quiet" disabled={busy} onClick={() => void act("cancel")}>Cancel this demo</button>
    </section>}
    {schedule?.class_phase === "ringing" && <section className={`card stack ${styles.alarm}`} role="alert" aria-label="Class alarm">
      <h2>It’s time for Maths!</h2>
      <p>{schedule.preparation === "ready" ? "Your lesson is ready. Start now or borrow five minutes." : "The class time has arrived. The lesson is still preparing; you can borrow five minutes."}</p>
      <div className="row"><button className="btn btn-primary" disabled={busy || schedule.preparation !== "ready"} onClick={() => void act("start")}>Start class</button>
        <button className="btn" disabled={busy} onClick={() => void act("borrow")}>Borrow 5 minutes</button></div>
    </section>}
    {schedule?.class_phase === "completed" && <p className="notice">The Maths lesson is complete. Your break is next.</p>}
    {schedule && <section className="stack"><h2>Your timetable</h2><ol className={styles.slots}>
      {schedule.slots.map((slot, i) => <li key={i} className={`${styles.slot} ${slot.subject === "break" ? styles.breakSlot : ""}`}>
        <strong>{slot.title}</strong><span>{timeText(slot.start_ms)} – {timeText(slot.end_ms)}</span>
        {!slot.content_available && <small>Matched lesson cards needed before this class can run.</small>}
      </li>)}
    </ol></section>}
    {error && <p className="error" role="alert">{error}</p>}
    <p className={styles.note}>Review demo only. Science and English are timetable placeholders until their matching cards are available. No student records or progress are saved.</p>
  </div>;
}
