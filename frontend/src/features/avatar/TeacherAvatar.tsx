"use client";

import { useEffect, useRef, useState } from "react";
import type { TalkingHead } from "@met4citizen/talkinghead";
import { AvatarVoice, type AvatarVoiceSink } from "./avatar-voice";
import { TeacherAvatar2D } from "./TeacherAvatar2D";
import styles from "./avatar.module.css";
import type { AvatarPhase } from "./types";

// The 3D teacher follows the selected voice: a female voice shows /avatars/teacher.glb and a male voice shows
// /avatars/teacher-male.glb (Mixamo-compatible rigs with ARKit and Oculus viseme blendshapes; see
// docs/voice/TEACHER_AVATAR_INTEGRATION.md). If the first model is missing or cannot load, the 2D cartoon teacher is shown; if
// only a later switch fails, the current teacher stays. Set NEXT_PUBLIC_EDAPTIVE_3D_AVATAR=0 to always use the 2D one.
// To try another GLB in /avatars for both voices, open the page with ?avatar=<name>
// (and optionally ?view=full|mid|upper|head; mid is the default, and gestures need it: hands are out of frame in upper/head).

/** The one standing pose she keeps (TalkingHead's `side`: relaxed, arms down). Other names: straight, hip, wide, turn. */
const STANCE = "side";
const HOLD_STANCE_SECONDS = 10_000_000;
const VIEWS = ["full", "mid", "upper", "head"];
/** Kokoro voice ids are language + gender + "_" + name: `af_heart` (female), `am_michael` (male). */
const MALE_VOICE = /^[a-z]m_/;
const DEFAULT_VOICE = "af_heart";

type Model = { url: string; body: "F" | "M" };

function settings() {
  const query = new URLSearchParams(window.location.search);
  const view = query.get("view") ?? "";
  const avatar = query.get("avatar") ?? "";
  return {
    wanted: process.env.NEXT_PUBLIC_EDAPTIVE_3D_AVATAR !== "0",
    view: VIEWS.includes(view) ? view : "mid", // waist-up: the face stays large and raised hands are in frame
    override: /^[a-z0-9-]{1,40}$/.test(avatar) ? avatar : "",
  };
}

function modelFor(voice: string): Model {
  const { override } = settings();
  const body = MALE_VOICE.test(voice) ? "M" : "F";
  if (override) return { url: `/avatars/${override}.glb`, body };
  return { url: body === "M" ? "/avatars/teacher-male.glb" : "/avatars/teacher.glb", body };
}

function webglAvailable() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch { return false; }
}

async function show(head: TalkingHead, model: Model) {
  head.start(); // switching teachers after Pause must render the new model too
  await head.showAvatar({ url: model.url, body: model.body, avatarMood: "happy", lipsyncLang: "en" });
  // By default TalkingHead picks a new random stance every 5 to 30 s (hand on hip, wide, turned...). A teacher
  // should stand steadily: holding one pose for this long postpones every idle pose change.
  await head.playPose(STANCE, null, HOLD_STANCE_SECONDS);
}

/**
 * The 3D teacher (TalkingHead). Hand `onVoice` to `new LiveNarrator(sink)` and the avatar plays the
 * narration itself with its mouth driven by the words; blinking, eye contact and idle motion are the
 * library's own. `voice` picks the model (female or male teacher). If WebGL or the model is unavailable, the 2D
 * teacher is shown instead and the narrator plays the sound as before.
 */
export function TeacherAvatar({ phase, analyser, voice = DEFAULT_VOICE, onVoice, onReady }: {
  phase: AvatarPhase;
  analyser: AnalyserNode | null;
  voice?: string;
  onVoice?: (sink: AvatarVoiceSink | null) => void;
  onReady?: (ready: boolean) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<"loading" | "3d" | "2d">("loading");
  const [changing, setChanging] = useState(false); // a different teacher is loading; the old one is still on screen
  const announce = useRef(onVoice);
  const ready = useRef(onReady);
  const wanted = useRef(voice);
  const sync = useRef<() => Promise<void>>(async () => {});
  useEffect(() => { announce.current = onVoice; ready.current = onReady; wanted.current = voice; });

  useEffect(() => {
    let alive = true;
    let head: TalkingHead | null = null;
    let shown = "";
    let loading = false;

    const dispose = () => {
      const previous = head;
      head = null;
      if (!previous) return;
      try { previous.dispose(); } catch { /* a partially loaded renderer */ }
      if (previous.audioCtx?.state !== 'closed') void previous.audioCtx?.close().catch(() => {});
    };
    const fallback = () => {
      sync.current = async () => {};
      announce.current?.(null);
      dispose();
      if (alive) { setMode('2d'); ready.current?.(true); }
    };

    // Show the model that matches the selected voice. While one loads the old teacher stays on screen,
    // and a change made meanwhile is picked up when it finishes.
    sync.current = async () => {
      if (!head || loading) return;
      loading = true;
      try {
        for (;;) {
          const model = modelFor(wanted.current);
          if (model.url === shown) break;
          announce.current?.(null); // until the new teacher is ready, the narrator plays the sound itself
          ready.current?.(false);
          if (shown && alive) setChanging(true);
          try {
            await show(head, model);
            shown = model.url;
          } catch (error) {
            if (!shown) throw error; // the very first model failed: fall back to the 2D teacher
            break; // a later switch failed: keep the teacher already on screen
          }
          if (!alive || !head) return;
        }
      } finally {
        loading = false;
        if (alive) setChanging(false);
      }
      if (alive) {
        announce.current?.(new AvatarVoice(head, fallback));
        ready.current?.(true);
      }
    };

    void (async () => {
      try {
        if (!settings().wanted) throw new Error("The 3D teacher is switched off.");
        if (!webglAvailable()) throw new Error("WebGL is not available.");
        // Loaded in the browser only: three.js and the audio worklet cannot run during server rendering.
        const [{ TalkingHead: Head }, { LipsyncEn }] = await Promise.all([
          import("@met4citizen/talkinghead"),
          import("@met4citizen/talkinghead/modules/lipsync-en.mjs"),
        ]);
        if (!alive || !host.current) return;
        head = new Head(host.current, {
          ttsEndpoint: "", // no text-to-speech inside the avatar; audio comes from the voice service
          dracoDecoderPath: '/avatars/draco/', // bundled models are uncompressed; never use the library's CDN default
          lipsyncModules: [], // its runtime import() of lip-sync files cannot be bundled; English is registered below
          lipsyncLang: "en",
          pcmSampleRate: 24000,
          cameraView: settings().view,
          cameraDistance: 1, // a little further back than the default, so a gesture's reach stays in frame
          cameraRotateEnable: false,
          cameraPanEnable: false,
          cameraZoomEnable: false,
          avatarMood: "happy",
          modelFPS: 30,
        });
        head.lipsync.en = new LipsyncEn();
        const hooks = window as { __gestures?: unknown[]; __head?: unknown }; // test hook: exposes the avatar only to tests
        if (hooks.__gestures) hooks.__head = head;
        await sync.current();
        if (alive) setMode("3d");
      } catch {
        fallback();
      }
    })();

    return () => {
      alive = false;
      announce.current?.(null);
      ready.current?.(false);
      dispose();
    };
  }, []);

  // The voice dropdown changed: switch to that teacher.
  useEffect(() => { void sync.current(); }, [voice]);

  if (mode === "2d") return <TeacherAvatar2D phase={phase} analyser={analyser} />;
  return (
    <div className={styles.stage3d} role="img" aria-label="Your teacher">
      <div ref={host} className={styles.host} />
      {mode === "loading" && <p className={styles.loading}>Your teacher is getting ready…</p>}
      {changing && <p className={styles.changing} role="status">Changing teacher…</p>}
    </div>
  );
}
