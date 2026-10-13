"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { LiveNarrator } from "@/features/voice";
import { getPreviewLesson, type PreviewLesson } from "@/lib/voice-preview-api";
import { deliveryAction, getDeliveryLesson, type DeliveryContext } from "@/lib/lesson-delivery-api";
import styles from "./lesson-player.module.css";

type Phase = "ready" | "preparing" | "playing" | "paused" | "complete";
const LABELS: Record<string, string> = {
  hook: "Let’s begin", lecture: "Explore the idea", worked_example: "Work it out together",
  transition: "Your turn", question: "Think it through", watch_out: "Look a little closer", recap: "What we learned",
};

function PlayIcon({ paused }: { paused: boolean }) {
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
    {paused ? <><path d="M8 5v14M16 5v14" /></> : <path d="m8 5 11 7-11 7Z" />}
  </svg>;
}

export function LessonPlayer({ scheduleId, onFinished, autoStart = false, delivery }: { delivery?: DeliveryContext; scheduleId?: string; onFinished?: () => void; autoStart?: boolean } = {}) {
  const timetableId = delivery?.timetableId;
  const slotId = delivery?.slotId;
  const stableDelivery = useMemo(() => timetableId && slotId ? { timetableId, slotId } : undefined, [timetableId, slotId]);
  const [lesson, setLesson] = useState<PreviewLesson | null>(null);
  const [error, setError] = useState("");
  const [index, setIndex] = useState(0);
  const [voice, setVoice] = useState("af_heart");
  const [phase, setPhase] = useState<Phase>("ready");
  const [caption, setCaption] = useState(-1);
  const narrator = useRef<LiveNarrator | null>(null);
  const generation = useRef(0);
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [reload, setReload] = useState(0);
  const autoStarted = useRef(false);
  const startButton = useRef<HTMLButtonElement | null>(null);

  function stop() {
    generation.current++;
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    advanceTimer.current = null;
    narrator.current?.cancel(); narrator.current = null;
  }

  useEffect(() => {
    const controller = new AbortController();
    (stableDelivery ? getDeliveryLesson(stableDelivery, controller.signal) : getPreviewLesson(controller.signal, scheduleId)).then(data => { setLesson(data); if ("position" in data) setIndex(data.position as number); }).catch(e => {
      if (!controller.signal.aborted) setError(e.message);
    });
    return () => controller.abort();
  }, [reload, scheduleId, stableDelivery]);

  useEffect(() => () => {
    generation.current++;
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    narrator.current?.cancel();
  }, []);

  useEffect(() => {
    if (!lesson || !autoStart || autoStarted.current) return;
    autoStarted.current = true;
    const timer = setTimeout(() => startButton.current?.click(), 0);
    return () => clearTimeout(timer);
  }, [lesson, autoStart]);

  async function move(partIndex: number, data = lesson, selectedVoice = voice) {
    try {
      if (delivery) await deliveryAction(delivery, "position", partIndex);
      start(partIndex, data, selectedVoice);
    } catch (e) { setError((e as Error).message); setPhase("ready"); }
  }

  function start(partIndex: number, data = lesson, selectedVoice = voice) {
    if (!data) return;
    stop();
    setIndex(partIndex); setCaption(-1); setPhase("preparing"); setError("");
    const token = generation.current;
    const part = data.segments[partIndex];
    const engine = new LiveNarrator(); narrator.current = engine;
    void engine.speak(part.id, selectedVoice, {
      onPlaying: () => { if (generation.current === token) setPhase("playing"); },
      onCaption: current => { if (generation.current === token) setCaption(current); },
      onComplete: () => {
        if (generation.current !== token) return;
        setPhase("complete");
        if (partIndex === data.segments.length - 1) onFinished?.();
        if (!part.checkpoint && partIndex + 1 < data.segments.length) {
          advanceTimer.current = setTimeout(() => void move(partIndex + 1, data, selectedVoice), 600);
        }
      },
    }, scheduleId, delivery).catch(e => {
      if (generation.current === token) { setError(e.message); setPhase("ready"); }
    });
  }

  async function primary() {
    if (!lesson) return;
    if (phase === "playing") { await narrator.current?.pause(); setPhase("paused"); }
    else if (phase === "paused") { await narrator.current?.resume(); setPhase("playing"); }
    else if (phase === "complete" && index + 1 < lesson.segments.length) void move(index + 1);
    else start(index);
  }

  async function navigate(next: number) {
    stop();
    if (delivery) { try { await deliveryAction(delivery, "position", next); } catch (e) { setError((e as Error).message); return; } } setIndex(next); setCaption(-1); setPhase("ready"); setError("");
  }

  if (!lesson) return <div className="stack">
    <Link className="wordmark" href="/">Edaptive</Link>
    <h1>Your lesson</h1>
    {error ? <><p className="error" role="alert">{error}</p><button className="btn" onClick={() => { setError(""); setReload(x => x + 1); }}>Try again</button></> : <p>Getting the lesson ready…</p>}
  </div>;

  const part = lesson.segments[index];
  const last = index === lesson.segments.length - 1;
  const label = phase === "playing" ? "Pause" : phase === "paused" ? "Keep listening" : phase === "preparing" ? "Getting ready…" : phase === "complete" ? (last ? "Listen again" : "Continue") : "Listen";
  const percent = Math.round(((index + (phase === "complete" ? 1 : 0)) / lesson.segments.length) * 100);

  return <div className={`stack ${styles.player}`}>
    <header className="row spread">
      <Link className="wordmark" href="/">Edaptive</Link>
      <span className={styles.preview}>{delivery ? "Scheduled lesson" : "Draft lesson preview"}</span>
    </header>
    <div className={styles.heading}>
      <div className="eyebrow">{lesson.subject === "math" ? "Maths" : lesson.subject} · Grade {lesson.grade}</div>
      <h1>{lesson.title}</h1>
      <p>Listen, explore, and take time to think.</p>
    </div>
    <div className={`row spread ${styles.settings}`}>
      <label className={styles.voiceLabel}>Teacher voice
        <select className="input" value={voice} onChange={e => { stop(); setVoice(e.target.value); setPhase("ready"); setCaption(-1); }}>
          {lesson.voices.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
        </select>
      </label>
      <div className={styles.progressWrap}>
        <span>Part {index + 1} of {lesson.segments.length}</span>
        <progress value={percent} max="100" aria-label="Lesson progress" />
      </div>
    </div>
    <section className={`card ${styles.lessonCard}`} aria-label="Current lesson part">
      <div className={styles.partLabel}>{LABELS[part.kind] ?? "Learn together"}</div>
      <div className={styles.lessonText}>
        {part.utterances.map((u, i) => <span key={`${part.id}-${i}`} className={caption === i ? styles.activeSentence : ""}>{u.caption} </span>)}
      </div>
      {part.cues.length > 0 && <aside className={styles.cue} aria-label="Visual cue caption">
        <strong>Picture cue</strong>
        {part.cues.map(cue => <p key={cue}>{cue}</p>)}
      </aside>}
      {part.checkpoint && phase === "complete" && <p className={styles.thinking} role="status">Take a moment to think. Continue when you’re ready.</p>}
      {last && phase === "complete" && <p className={styles.thinking} role="status">You’ve reached the end of this lesson.</p>}
    </section>
    <div className={styles.controls}>
      <button className="btn" disabled={index === 0} onClick={() => navigate(index - 1)}>Previous</button>
      <button ref={startButton} className="btn btn-primary" disabled={phase === "preparing"} onClick={() => void primary()}><PlayIcon paused={phase === "playing"} />{label}</button>
      <button className="btn" disabled={phase === "preparing"} onClick={() => start(index)}>Replay this part</button>
      <button className="btn" disabled={last || (!!delivery && phase !== "complete")} onClick={() => void navigate(index + 1)}>Next</button>
    </div>
    <p className={styles.status} role="status">{phase === "preparing" ? "The teacher is getting ready to speak." : phase === "paused" ? "Paused. Keep listening when you’re ready." : phase === "playing" ? "Listen and follow the highlighted sentence." : "You can listen, replay or move through the lesson."}</p>
    {error && <p className="error" role="alert">{error}</p>}
    <p className={styles.draftNote}>{delivery ? "Your lesson position is saved. Draft cards are enabled for evaluation." : "Review preview: the lesson content is still a draft. Answers and progress are not recorded here."}</p>
  </div>;
}
