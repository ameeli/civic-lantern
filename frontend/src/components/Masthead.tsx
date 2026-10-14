import { headers } from "next/headers";
import CycleSelector from "@/components/CycleSelector";
import Gavel from "@/components/Gavel";
import MastheadRule from "@/components/MastheadRule";
import { formatMastheadDate } from "@/utils/formatMastheadDate";

export default async function Masthead({
  cycles,
  selectedCycle,
}: {
  cycles?: number[];
  selectedCycle?: number;
}) {
  // Vercel sets this from the reader's IP, so the date is theirs, not the server's UTC.
  const timeZone = (await headers()).get("x-vercel-ip-timezone");
  const dateLine = formatMastheadDate(new Date(), timeZone);
  return (
    <div className="col-span-12 flex flex-col items-center lg:mt-0">
      <div className="relative w-full flex justify-center mb-6">
        <div className="hidden lg:flex absolute left-0 bottom-0 flex-col text-md font-medium leading-tight">
          <span>{dateLine}</span>
        </div>
        <h1 className="text-masthead text-3xl">The Civic Lantern</h1>
        {cycles && selectedCycle !== undefined && (
          <div className="hidden lg:flex absolute right-0 bottom-0">
            <CycleSelector cycles={cycles} selectedCycle={selectedCycle} />
          </div>
        )}
      </div>
      <div className="flex lg:hidden flex-col items-center text-md font-medium leading-tight">
        <span>{dateLine}</span>
        {cycles && selectedCycle !== undefined && (
          <CycleSelector cycles={cycles} selectedCycle={selectedCycle} />
        )}
      </div>
      <MastheadRule>
        <Gavel width={40} height={40} />
      </MastheadRule>
    </div>
  );
}
