import ElectionSpendingSection from "@/components/ElectionSpendingSection";
import SpendingPackChartSection from "@/components/SpendingPackChartSection";
import CycleSelector from "@/components/CycleSelector";
import Gavel from "@/components/Gavel";
import MastheadRule from "@/components/MastheadRule";
import PaperBorder from "@/components/PaperBorder";
import { listReadyCycles } from "@/api/spending";
import { resolveCycle } from "@/utils/resolveCycle";

// This page fetches live spending data from an external backend on every
// load. Prerendering it at build time couples build success to that
// backend being reachable right then — force per-request rendering instead.
export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: PageProps<"/">) {
  const params = await searchParams;
  const readyCycles = await listReadyCycles();
  const cycle = resolveCycle(params.cycle, readyCycles);

  return (
    <div className="flex flex-col flex-1 items-center bg-dark-wood font-sans">
      <main className="relative isolate grid grid-cols-12 content-start gap-x-4 gap-y-1 w-full max-w-6xl my-2 p-12 lg:p-15">
        <PaperBorder />
        <div className="col-span-12 flex flex-col items-center gap-5 mt-4 lg:mt-0">
          <h1 className="text-masthead text-3xl">The Civic Lantern</h1>
          <MastheadRule>
            <Gavel width={40} height={40} />
          </MastheadRule>
        </div>
        <div className="col-span-12 mb-3 flex flex-col items-center gap-2">
          <h1 className="font-headline font-semibold text-3xl text-center">
            Direct vs. Outside Money: Federal Campaign Spending Breakdowns
          </h1>
          {cycle !== undefined && (
            <CycleSelector cycles={readyCycles} selectedCycle={cycle} />
          )}
        </div>
        {cycle !== undefined ? (
          <>
            <ElectionSpendingSection cycle={cycle} />
            <SpendingPackChartSection cycle={cycle} />
          </>
        ) : (
          <div className="col-span-12 text-center text-body-justify">
            No election cycle data available yet.
          </div>
        )}
      </main>
    </div>
  );
}
