"use client";

interface ChartBreadcrumbProps {
  path: string[];
  onNavigate: (depth: number) => void;
}

export default function ChartBreadcrumb({
  path,
  onNavigate,
}: ChartBreadcrumbProps) {
  return (
    <nav className="absolute top-1 z-10 flex w-full justify-center items-center text-sm font-headline font-semibold italic">
      {path.map((segment, i) => {
        const isLast = i === path.length - 1;
        const base =
          "crumb-shape pl-5 pr-5 py-1.5 bg-[var(--color-ink)]/20 text-breadcrumb-text";

        if (isLast) {
          return (
            <span key={i} className={base}>
              <span className="block max-w-[min(45vw,220px)] truncate">
                {segment}
              </span>
            </span>
          );
        }

        return (
          <button
            key={i}
            onClick={() => onNavigate(i)}
            className={`${base} cursor-pointer hover:bg-(--color-ink)/40`}
          >
            <span className="block max-w-[min(45vw,220px)] truncate">
              {segment}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
