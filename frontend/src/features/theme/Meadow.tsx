import { Duck, Kid, Tree } from "./drawings";

// A little meadow at the end of the child's home page: two children wave, a duck swims in the pond.
// Decorative only (hidden in the Storybook look).
export function Meadow() {
  return (
    <div className="ui-meadow ui-playful-only" aria-hidden>
      <svg viewBox="0 0 760 210" focusable="false">
        <path d="M300 170c-50-10-60-52-8-70 62-22 168-20 220 8 44 24 26 62-26 74-60 14-130 6-186-12z" fill="var(--pond)" />
        <Duck x={410} y={150} />
        <Tree x={70} y={176} s={0.85} tone="var(--tree-light)" />
        <Tree x={690} y={184} s={0.7} />
        <Kid x={150} y={186} dress="#f4cfe0" hair="#e8c37a" delay={0.2} />
        <Kid x={214} y={192} dress="#cfe4f2" hair="#a98c68" tall={0.82} delay={1.1} />
        <path d="M110 190h140" fill="none" stroke="var(--line)" strokeWidth="2" strokeLinecap="round" opacity=".35" />
      </svg>
    </div>
  );
}
