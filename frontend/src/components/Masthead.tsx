import CycleSelector from "@/components/CycleSelector";
import Gavel from "@/components/Gavel";
import MastheadRule from "@/components/MastheadRule";

function ordinalSuffix(day: number) {
  if (day >= 11 && day <= 13) return "th";
  switch (day % 10) {
    case 1:
      return "st";
    case 2:
      return "nd";
    case 3:
      return "rd";
    default:
      return "th";
  }
}

function formatMastheadDate(date: Date) {
  const weekday = date.toLocaleDateString("en-US", { weekday: "long" });
  const month = date.toLocaleDateString("en-US", { month: "long" });
  const day = date.getDate();
  const year = date.getFullYear();
  return `${weekday}, ${month} ${day}${ordinalSuffix(day)}, ${year}`;
}

export default function Masthead({
  cycles,
  selectedCycle,
}: {
  cycles?: number[];
  selectedCycle?: number;
}) {
  const dateLine = formatMastheadDate(new Date());
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
