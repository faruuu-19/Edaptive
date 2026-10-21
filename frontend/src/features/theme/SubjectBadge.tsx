// A round subject badge shown only in the Playful look (hidden by CSS otherwise).
type Subject = "math" | "english" | "science" | "break" | string;

const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 2.4, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function Glyph({ subject }: { subject: Subject }) {
  if (subject === "math")
    return (
      <g {...stroke}>
        <path d="M7 4v7M3.5 7.5h7" />
        <path d="M14 7.5h7" />
        <path d="M4 15l6 6M10 15l-6 6" />
        <path d="M14 16.5h7M14 20h7" />
      </g>
    );
  if (subject === "english")
    return (
      <g {...stroke}>
        <path d="M2.5 5.5c3.5-1 6.5-.5 9.5 1.5 3-2 6-2.5 9.5-1.5v13c-3.5-1-6.5-.5-9.5 1.5-3-2-6-2.5-9.5-1.5z" />
        <path d="M12 7v13" />
      </g>
    );
  if (subject === "science")
    return (
      <g {...stroke}>
        <path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3" />
        <path d="M7.5 15h9" />
      </g>
    );
  return (
    <g {...stroke}>
      <path d="M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z" />
      <path d="M17 10h1.5a2.5 2.5 0 0 1 0 5H17" />
      <path d="M8 3.5c0 1.5 1.5 1.5 1.5 3M12 3.5c0 1.5 1.5 1.5 1.5 3" />
    </g>
  );
}

export function SubjectBadge({ subject, size = 44 }: { subject: Subject; size?: number }) {
  return (
    <span className="ui-badge ui-playful-only" data-subject={subject} aria-hidden>
      <svg width={size * 0.6} height={size * 0.6} viewBox="0 0 24 24">
        <Glyph subject={subject} />
      </svg>
    </span>
  );
}
