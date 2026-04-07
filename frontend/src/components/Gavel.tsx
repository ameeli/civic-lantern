export default function Gavel({
  width = 32,
  height = 32,
  className = "",
}: {
  width?: number;
  height?: number;
  fill?: string;
  className?: string;
}) {
  return (
    <svg
      fill="var(--color-ink)"
      width={width}
      height={height}
      viewBox="3.65 6.05 9.5 7.45"
      xmlns="http://www.w3.org/2000/svg"
      className={`ink-press ${className}`}
    >
      {/* Top cap */}
      <rect x="5.3" y="6.55" width="3.5" height="0.5" rx="0.4" />
      {/* Bottom cap */}
      <rect x="5.3" y="10.95" width="3.5" height="0.5" rx="0.4" />
      {/* Head */}
      <rect
        x="5.8"
        y="7.5"
        width="2.5"
        height="3"
        fill="none"
        stroke="var(--color-ink)"
        strokeWidth="0.35"
        rx="0.2"
      />
      {/* Handle */}
      <rect x="8.15" y="8.55" width="4" height="0.8" rx="0.4" />
      {/* Strike plate */}
      <rect x="4.15" y="12.08" width="5.5" height="0.9" rx="0.4" />
    </svg>
  );
}
