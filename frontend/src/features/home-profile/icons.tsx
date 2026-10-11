// Stroke icons drawn inline so they look identical on every machine (emoji don't).
type IconProps = { size?: number };

const svg = (size: number, children: React.ReactNode) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2.2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden
  >
    {children}
  </svg>
);

export const LockIcon = ({ size = 18 }: IconProps) =>
  svg(
    size,
    <>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </>,
  );

export const SwitchIcon = ({ size = 18 }: IconProps) =>
  svg(
    size,
    <>
      <path d="M16 3l4 4-4 4" />
      <path d="M20 7H4" />
      <path d="M8 21l-4-4 4-4" />
      <path d="M4 17h16" />
    </>,
  );

export const MathsIcon = ({ size = 44 }: IconProps) =>
  svg(
    size,
    <>
      <path d="M7 4v6M4 7h6" />
      <path d="M14 7h6" />
      <path d="M4.5 15.5l5 5M9.5 15.5l-5 5" />
      <path d="M14 16h6M14 20h6" />
    </>,
  );

export const BookIcon = ({ size = 44 }: IconProps) =>
  svg(
    size,
    <>
      <path d="M2 5h7a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H2z" />
      <path d="M22 5h-7a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h8z" />
    </>,
  );

export const FlaskIcon = ({ size = 44 }: IconProps) =>
  svg(
    size,
    <>
      <path d="M9 3h6" />
      <path d="M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3" />
      <path d="M7 15h10" />
    </>,
  );
