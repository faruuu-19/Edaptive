"use client";

import { useEffect, useRef } from "react";
import styles from "./avatar.module.css";
import type { AvatarPhase } from "./types";

// Geometry on teacher.webp (500 x 500), measured on the artwork: the drawn smile runs from the left
// corner through its lowest point to the right corner. An open mouth reuses that exact curve.
const MOUTH = { x: 248, cornerY: 211, half: 31, smileLow: 227.5, upperLow: 214, maxOpen: 11 };
// Voice energy sits well below full scale; these map the analyser's level onto 0..1 of mouth opening.
const LEVEL_FLOOR = 0.015;
const LEVEL_RANGE = 0.13;

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

/**
 * The teacher. The mouth follows the narration's real audio level, so it moves with the speech,
 * freezes when the audio clock is paused and closes when nothing is playing. Level comes from the
 * `analyser` that `LiveNarrator` exposes; this component never touches audio or the network.
 */
export function TeacherAvatar2D({ phase, analyser }: { phase: AvatarPhase; analyser: AnalyserNode | null }) {
  const bob = useRef<SVGGElement>(null);
  const cavity = useRef<SVGPathElement>(null);
  const clip = useRef<SVGPathElement>(null);
  const teeth = useRef<SVGEllipseElement>(null);
  const tongue = useRef<SVGEllipseElement>(null);

  useEffect(() => {
    const parts = { cavity: cavity.current, clip: clip.current, teeth: teeth.current, tongue: tongue.current, bob: bob.current };
    if (!parts.cavity || !parts.clip || !parts.teeth || !parts.tongue || !parts.bob) return;
    const samples = new Float32Array(analyser?.fftSize ?? 1);
    const spectrum = new Uint8Array(analyser?.frequencyBinCount ?? 1);
    let open = 0;
    let wide = 1;
    let frame = 0;

    const draw = () => {
      let target = 0;
      let shape = 1;
      if (analyser && phase === "playing") {
        analyser.getFloatTimeDomainData(samples);
        let sum = 0;
        for (const value of samples) sum += value * value;
        target = clamp((Math.sqrt(sum / samples.length) - LEVEL_FLOOR) / LEVEL_RANGE, 0, 1);
        // Brighter sound (ee, s) widens the mouth; darker sound (oo, o) rounds it.
        analyser.getByteFrequencyData(spectrum);
        let weighted = 0;
        let total = 0;
        spectrum.forEach((magnitude, bin) => { weighted += magnitude * bin; total += magnitude; });
        if (total > 0) shape = clamp(0.8 + (weighted / total / spectrum.length) * 2.2, 0.78, 1.12);
      }
      // A quick attack and a slower release read as a jaw, not a flicker.
      open += (target - open) * (target > open ? 0.55 : 0.25);
      wide += (shape - wide) * 0.2;
      const height = open * MOUTH.maxOpen;
      const left = MOUTH.x - MOUTH.half * wide;
      const right = MOUTH.x + MOUTH.half * wide;
      const upperLow = MOUTH.upperLow;
      const lowerLow = MOUTH.smileLow + height;
      // A quadratic through the corners reaches (corner + control) / 2 at its middle.
      const upperControl = 2 * upperLow - MOUTH.cornerY;
      const lowerControl = 2 * lowerLow - MOUTH.cornerY;
      const outline = `M${left} ${MOUTH.cornerY}Q${MOUTH.x} ${upperControl} ${right} ${MOUTH.cornerY}Q${MOUTH.x} ${lowerControl} ${left} ${MOUTH.cornerY}Z`;
      const visible = height > 0.5; // closed: the artwork's own smile shows
      parts.cavity!.setAttribute("d", outline);
      parts.cavity!.setAttribute("opacity", visible ? "1" : "0");
      parts.clip!.setAttribute("d", outline);
      parts.teeth!.setAttribute("opacity", visible && height > 2.5 ? "1" : "0");
      parts.teeth!.setAttribute("cy", String(upperLow + 1));
      parts.teeth!.setAttribute("rx", String(MOUTH.half * wide * 0.72));
      parts.teeth!.setAttribute("ry", String(clamp(height * 0.3, 0.01, 3.4)));
      parts.tongue!.setAttribute("opacity", visible && height > 4 ? "1" : "0");
      parts.tongue!.setAttribute("cy", String(lowerLow - 2));
      parts.tongue!.setAttribute("rx", String(MOUTH.half * wide * 0.42));
      parts.tongue!.setAttribute("ry", String(clamp(height * 0.34, 0.01, 5)));
      // The head dips a touch as the jaw opens.
      parts.bob!.style.setProperty("--dip", `${(open * 1.4).toFixed(2)}px`);
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [analyser, phase]);

  return (
    <div className={`${styles.frame} ${phase === "playing" ? styles.talking : ""}`} role="img" aria-label="Your teacher">
      <svg className={styles.art} viewBox="0 0 500 500" aria-hidden="true">
        <defs>
          <clipPath id="avatar-mouth"><path ref={clip} d="" /></clipPath>
        </defs>
        <g ref={bob} className={styles.bob}>
          <image href="/avatar/teacher.webp" width="500" height="500" />
          <path ref={cavity} d="" fill="#6b2128" stroke="#3a1214" strokeWidth="1.8" strokeLinejoin="round" opacity="0" />
          <g clipPath="url(#avatar-mouth)">
            <ellipse ref={teeth} cx={MOUTH.x} cy={MOUTH.upperLow} rx="20" ry="0.01" fill="#fffaf2" opacity="0" />
            <ellipse ref={tongue} cx={MOUTH.x} cy={MOUTH.smileLow} rx="12" ry="0.01" fill="#e8726f" opacity="0" />
          </g>
        </g>
      </svg>
    </div>
  );
}
