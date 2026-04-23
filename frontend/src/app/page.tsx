import { Suspense } from "react";
import ElectionSpendingSection from "@/components/ElectionSpendingSection";
import Gavel from "@/components/Gavel";
import MastheadRule from "@/components/MastheadRule";
import PaperBorder from "@/components/PaperBorder";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center bg-dark-wood font-sans">
      <main className="relative isolate grid grid-cols-12 content-start gap-1 flex-1 w-full max-w-7xl my-2 p-12 lg:p-15">
        <PaperBorder />
        <div className="col-span-12 flex flex-col items-center gap-5">
          <h1 className="text-masthead text-3xl">The Civic Lantern</h1>
          <MastheadRule>
            <Gavel width={40} height={40} />
          </MastheadRule>
        </div>
        <ElectionSpendingSection cycle={2024} />
      </main>
    </div>
  );
}
