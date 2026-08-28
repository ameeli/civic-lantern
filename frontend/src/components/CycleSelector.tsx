"use client";

import { usePathname, useRouter } from "next/navigation";

export default function CycleSelector({
  cycles,
  selectedCycle,
}: {
  cycles: number[];
  selectedCycle: number;
}) {
  const router = useRouter();
  const pathname = usePathname();

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    router.push(`${pathname}?cycle=${e.target.value}`);
  }

  return (
    <label className="flex items-center gap-2 font-headline text-sm font-semibold">
      Election Cycle:
      <select
        aria-label="Election Cycle"
        value={selectedCycle}
        onChange={handleChange}
        className="border-ink-thin bg-transparent px-2 py-1 font-headline text-sm cursor-pointer"
      >
        {cycles.map((cycle) => (
          <option key={cycle} value={cycle}>
            {cycle}
          </option>
        ))}
      </select>
    </label>
  );
}
