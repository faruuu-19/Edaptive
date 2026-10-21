// Hairline drawings shared by the scenery and the meadow footer (Playful look only).
export const LINE = "var(--line)";

export function Tree({ x, y, s = 1, tone = "var(--tree)" }: { x: number; y: number; s?: number; tone?: string }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} fill="none" stroke={LINE} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M0 0v-46" />
      <path d="M0 -46c-26 0-38-22-30-44 6-18 24-30 30-30s24 12 30 30c8 22-4 44-30 44z" fill={tone} />
      <path d="M0 -30c-9-6-11-14-10-22M0 -50c8-5 11-12 10-20" />
    </g>
  );
}

export function House({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`} fill="none" stroke={LINE} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M0 0V-120L100 -200 200 -120V0z" fill="#fbfcef" />
      {/* a heart-shaped window, as in the reference */}
      <path d="M100 -22c-34-22-52-40-52-62 0-18 14-30 30-30 11 0 18 6 22 14 4-8 11-14 22-14 16 0 30 12 30 30 0 22-18 40-52 62z" fill="var(--hill-light)" />
    </g>
  );
}

export function Duck({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <g className="ui-duck-swim">
        <ellipse className="ui-ripple" cx="0" cy="26" rx="46" ry="7" fill="none" stroke="#fff" strokeWidth="2" opacity=".8" />
        <g className="ui-duck-bob" fill="#fff" stroke={LINE} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <ellipse cx="0" cy="12" rx="52" ry="8" fill="rgba(255,255,255,.55)" stroke="none" />
          <path d="M-26 -2c0 14 12 18 28 18 18 0 30-8 30-22-8 4-14 2-18-6-4-10-14-16-22-12-10 4-18 10-18 22z" />
          <circle cx="-14" cy="-20" r="9" />
          <path d="M-24 -20l-10 4 10 3z" fill="#f2c36b" />
          <circle cx="-15" cy="-22" r="1.6" fill={LINE} stroke="none" />
        </g>
      </g>
    </g>
  );
}

export function Kid({ x, y, dress, hair, tall = 1, delay = 0 }: { x: number; y: number; dress: string; hair: string; tall?: number; delay?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${tall})`} fill="none" stroke={LINE} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="0" cy="-92" r="15" fill="#fdf0e2" />
      <path d="M-15 -94c-2-18 10-24 17-22 12 1 16 12 13 22-6-8-16-10-30 0z" fill={hair} />
      <path d="M-8 -80c-14 8-20 30-24 56h64c-4-26-10-48-24-56z" fill={dress} />
      <path d="M-8 -66c-12 6-18 14-20 24" />
      {/* the raised arm waves from the shoulder */}
      <g className="ui-wave-arm" style={{ animationDelay: `${delay}s` }}>
        <path d="M8 -68L27 -96" />
        <circle cx="28.5" cy="-98" r="4" fill="#fdf0e2" />
      </g>
      <path d="M-10 -24v22M10 -24v22" />
      <circle cx="-5" cy="-92" r=".9" fill={LINE} />
      <circle cx="5" cy="-92" r=".9" fill={LINE} />
      <path d="M-4 -86c3 3 5 3 8 0" strokeWidth="1.6" />
    </g>
  );
}
