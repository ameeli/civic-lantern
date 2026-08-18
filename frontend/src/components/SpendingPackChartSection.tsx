import { listCandidatesSpending } from "@/api/spending";
import SpendingPackChart from "./SpendingPackChart";

export default async function SpendingPackChartSection({
  cycle,
}: {
  cycle: number;
}) {
  const { items } = await listCandidatesSpending({
    cycle,
    sort_by: "outside_total",
    order: "desc",
    limit: 500,
  });
  return (
    <div className="col-span-12 sm:col-span-12 lg:col-span-8 mt-8 lg:mt-0 border-ink-thin">
      <SpendingPackChart data={items} />
    </div>
  );
}
