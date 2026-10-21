// Pip, Edaptive's friendly helper. Drawn from rounded shapes only (no points), decorative, shown only in the Playful look.
export function Pip({ size = 150, waving = false, className = "" }: { size?: number; waving?: boolean; className?: string }) {
  return (
    <svg
      className={`ui-pip ui-playful-only ${className}`}
      data-waving={waving || undefined}
      width={size}
      height={size * 1.16}
      viewBox="0 0 130 150"
      aria-hidden
      focusable="false"
    >
      <ellipse cx="65" cy="143" rx="34" ry="6" fill="#37483b" opacity=".14" />
      {/* feet */}
      <rect x="38" y="124" width="22" height="14" rx="7" fill="#f3d58d" stroke="#37483b" strokeWidth="2.1" />
      <rect x="70" y="124" width="22" height="14" rx="7" fill="#f3d58d" stroke="#37483b" strokeWidth="2.1" />
      {/* resting arm */}
      <path d="M22 84c-9 4-12 16-8 24" fill="none" stroke="#37483b" strokeWidth="2.1" strokeLinecap="round" />
      {/* body */}
      <path d="M65 28c27 0 44 20 44 52 0 30-15 49-44 49S21 110 21 80c0-32 17-52 44-52z" fill="#cfe6c3" stroke="#37483b" strokeWidth="2.2" />
      <path d="M65 58c17 0 28 13 28 33 0 19-9 31-28 31S37 110 37 91c0-20 11-33 28-33z" fill="#fffdf3" />
      {/* sprout */}
      <path d="M65 28c0-7 1-12 3-16" fill="none" stroke="#37483b" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M68 14c4-9 14-10 19-6-1 8-9 12-19 6z" fill="#8cc272" stroke="#37483b" strokeWidth="2.1" strokeLinejoin="round" />
      <path d="M66 17c-3-7-11-9-16-5 1 7 8 10 16 5z" fill="#b7dc9c" stroke="#37483b" strokeWidth="2.1" strokeLinejoin="round" />
      {/* face */}
      <circle cx="49" cy="64" r="9" fill="#fff" stroke="#37483b" strokeWidth="2" />
      <circle cx="81" cy="64" r="9" fill="#fff" stroke="#37483b" strokeWidth="2" />
      <circle cx="51" cy="65" r="4" fill="#37483b" />
      <circle cx="83" cy="65" r="4" fill="#37483b" />
      <circle cx="52.5" cy="63" r="1.4" fill="#fff" />
      <circle cx="84.5" cy="63" r="1.4" fill="#fff" />
      <ellipse cx="40" cy="80" rx="6" ry="4" fill="#f6c1ad" opacity=".8" />
      <ellipse cx="90" cy="80" rx="6" ry="4" fill="#f6c1ad" opacity=".8" />
      <path d="M56 78c3 6 15 6 18 0" fill="none" stroke="#37483b" strokeWidth="2.2" strokeLinecap="round" />
      {/* waving arm */}
      <g className="ui-pip-arm">
        <path d="M108 86c10-3 17-13 14-24" fill="none" stroke="#37483b" strokeWidth="2.1" strokeLinecap="round" />
        <circle cx="122" cy="60" r="6.5" fill="#fffdf3" stroke="#37483b" strokeWidth="2" />
      </g>
    </svg>
  );
}
