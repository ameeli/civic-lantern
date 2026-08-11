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
  // console.log("items:", items);
  return (
    <div className="col-span-12 sm:col-span-12 lg:col-span-7 space-y-3">
      <h1 className="font-headline font-semibold text-2xl text-center">
        SPENDING BREAKDOWNS
      </h1>
      <SpendingPackChart data={items} />
    </div>
  );
}
