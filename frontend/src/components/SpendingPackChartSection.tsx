import { fetchAllCandidatesForOffice } from "@/api/spending";
import SpendingPackChart from "./SpendingPackChart";

export default async function SpendingPackChartSection({
  cycle,
}: {
  cycle: number;
}) {
  const [P, S, H] = await Promise.all([
    fetchAllCandidatesForOffice(cycle, "P"),
    fetchAllCandidatesForOffice(cycle, "S"),
    fetchAllCandidatesForOffice(cycle, "H"),
  ]);
  return (
    <div className="col-span-12 sm:col-span-12 lg:col-span-8 mt-8 lg:mt-0 border-ink-thin">
      <SpendingPackChart data={{ P, S, H }} />
    </div>
  );
}
