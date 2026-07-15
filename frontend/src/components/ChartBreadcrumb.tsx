"use client";

interface ChartBreadcrumbProps {
  path: string[];
  onNavigate: (depth: number) => void;
}

export default function ChartBreadcrumb({
  path,
  onNavigate,
}: ChartBreadcrumbProps) {
  if (path.length === 0) return null;

  return (
    <nav className="flex items-center gap-1 text-sm font-headline italic ink-press">
      {path.map((segment, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <span className="opacity-40">→</span>}
          <button onClick={() => onNavigate(i)} className="hover:underline">
            {segment}
          </button>
        </span>
      ))}
    </nav>
  );
}
