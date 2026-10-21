"use client";

import { usePathname } from "next/navigation";

import { Duck, House, Kid, LINE, Tree } from "./drawings";

// Soft picture-book scenery behind every screen in the Playful look (hidden by CSS in the Storybook look).
// Rolling sage hills, a pale line-drawn sun, a pond with a duck, thin line trees and a little house:
// flat fills and hairline drawings only. The picker gets the full scene, other child screens the meadow,
// and parent / setup / lesson screens a quiet version with no hills.
const CALM = ["/parent", "/setup", "/lesson-preview", "/lesson-demo"];

export function Scenery() {
  const path = usePathname() ?? "/";
  const scene = path === "/" ? "picker" : CALM.some((p) => path === p || path.startsWith(p + "/")) ? "calm" : "meadow";

  return (
    <div className="ui-scenery" data-scene={scene} aria-hidden>
      <div className="ui-sky" />
      {/* pale mint cloud fields in the top corners */}
      <svg className="ui-blob ui-blob-a" viewBox="0 0 500 360" focusable="false">
        <path d="M60 300c-60-40-60-130 10-170 30-60 110-90 170-60 40-50 130-50 170 10 50-10 100 30 90 90 30 40 10 110-40 130H120c-30 10-50 10-60 0z" fill="var(--mint)" />
      </svg>
      <svg className="ui-blob ui-blob-b" viewBox="0 0 500 360" focusable="false">
        <path d="M30 120C20 40 120-20 200 20c50-40 150-30 190 30 70 0 110 70 70 130 20 60-20 120-90 120H110c-80 0-130-80-80-180z" fill="var(--mint)" opacity=".7" />
      </svg>
      {/* a thin line-drawn sun */}
      <svg className="ui-sunny" viewBox="0 0 160 160" focusable="false">
        <circle cx="80" cy="80" r="30" fill="var(--lemon)" stroke={LINE} strokeWidth="2.2" />
        <g stroke={LINE} strokeWidth="2.2" strokeLinecap="round">
          {Array.from({ length: 10 }, (_, i) => (
            <line key={i} x1="80" y1="22" x2="80" y2="36" transform={`rotate(${i * 36} 80 80)`} />
          ))}
        </g>
      </svg>
      <svg className="ui-cloud ui-cloud-a" viewBox="0 0 200 90" focusable="false">
        <path d="M52 82c-24 0-42-9-42-28 0-17 15-26 32-25C48 14 64 4 85 6c17 2 29 12 34 25 26-6 58 4 58 29 0 15-13 22-32 22z" fill="#fff" opacity=".9" />
      </svg>
      <svg className="ui-cloud ui-cloud-b" viewBox="0 0 200 90" focusable="false">
        <path d="M52 82c-24 0-42-9-42-28 0-17 15-26 32-25C48 14 64 4 85 6c17 2 29 12 34 25 26-6 58 4 58 29 0 15-13 22-32 22z" fill="#fff" opacity=".8" />
      </svg>

      <svg className="ui-land" viewBox="0 0 1440 900" preserveAspectRatio="none" focusable="false">
        <path d="M0 330C140 250 300 240 470 300s330 90 520 30c150-48 290-90 450-30v600H0z" fill="var(--hill-light)" />
        <path d="M0 560C170 500 330 500 520 550s380 70 520 20c150-54 290-60 400-20v350H0z" fill="var(--hill-mid)" />
        <path d="M0 760c180-40 360-44 560-12s420 40 560 0c120-34 220-30 320-6v158H0z" fill="var(--hill-front)" />
      </svg>

      {/* The scene items keep their own proportions, so they are separate from the stretched hills. */}
      <svg className="ui-vignette" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMax slice" focusable="false">
        <g className="ui-pond">
          <path d="M910 610c-60-10-70-60-10-84 70-30 190-26 250 8 50 28 30 74-30 88-70 16-150 6-210-12z" fill="var(--pond)" />
          <Duck x={1040} y={590} />
        </g>
        <g className="ui-house-group">
          <Tree x={1010} y={420} s={1.15} tone="var(--tree)" />
          <Tree x={1236} y={436} s={0.8} tone="var(--tree-light)" />
          <House x={760} y={470} />
          <Kid x={1070} y={500} dress="#f4cfe0" hair="#e8c37a" />
          <Kid x={1130} y={510} dress="#cfe4f2" hair="#a98c68" tall={0.82} delay={0.9} />
        </g>
        <g className="ui-small-trees">
          <Tree x={170} y={560} s={0.9} tone="var(--tree-light)" />
          <Tree x={300} y={590} s={0.65} />
        </g>
      </svg>
    </div>
  );
}
