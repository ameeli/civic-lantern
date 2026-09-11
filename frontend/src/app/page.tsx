import ElectionSpendingSection from "@/components/ElectionSpendingSection";
import SpendingPackChartSection from "@/components/SpendingPackChartSection";
import CycleSelector from "@/components/CycleSelector";
import Gavel from "@/components/Gavel";
import MastheadRule from "@/components/MastheadRule";
import PaperBorder from "@/components/PaperBorder";
import { listReadyCycles } from "@/api/spending";
import { resolveCycle } from "@/utils/resolveCycle";

export const dynamic = "force-dynamic";

function Masthead() {
  return (
    <div className="col-span-12 flex flex-col items-center gap-5 mt-4 lg:mt-0">
      <h1 className="text-masthead text-3xl">The Civic Lantern</h1>
      <MastheadRule>
        <Gavel width={40} height={40} />
      </MastheadRule>
    </div>
  );
}

export default async function Home({ searchParams }: PageProps<"/">) {
  const params = await searchParams;
  const readyCycles = await listReadyCycles();
  const cycle = resolveCycle(params.cycle, readyCycles);

  if (cycle === undefined) {
    return (
      <div className="relative isolate flex flex-col flex-1 items-center bg-dark-wood font-sans">
        <PaperBorder />
        <main className="grid grid-cols-12 content-start gap-x-4 gap-y-1 w-full max-w-6xl my-2 p-12 lg:p-15">
          <Masthead />
          <div className="col-span-12 text-center text-body-justify">
            No election cycle data available yet.
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="relative isolate flex flex-col flex-1 items-center bg-dark-wood font-sans">
      <PaperBorder />
      <main className="grid grid-cols-12 content-start gap-x-4 gap-y-1 w-full max-w-7xl p-12 lg:p-15 ">
        <Masthead />
        <div className="col-span-12 mb-3 flex flex-col items-center gap-2">
          <h1 className="font-headline font-semibold text-3xl text-center">
            Candidate Cash vs. Super PAC Millions: Who Truly Controls the
            Election Narrative?
          </h1>
          <CycleSelector cycles={readyCycles} selectedCycle={cycle} />
        </div>
        <ElectionSpendingSection cycle={cycle} />
        <SpendingPackChartSection cycle={cycle} />
      </main>
    </div>
  );
}
