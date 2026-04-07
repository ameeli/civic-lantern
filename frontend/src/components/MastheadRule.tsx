function Lines({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <div className="border-t-3 border-ink ink-press opacity-80" />
      <div className="border-t-2 border-ink ink-press opacity-50" />
    </div>
  );
}

export default function MastheadRule({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center w-full gap-2">
      <Lines className="flex-[3.1]" />
      {children}
      <Lines className="flex-[2.9]" />
    </div>
  );
}
