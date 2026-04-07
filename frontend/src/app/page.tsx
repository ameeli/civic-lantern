import Gavel from "@/components/Gavel";
import MastheadRule from "@/components/MastheadRule";
import PaperBorder from "@/components/PaperBorder";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center py-5 bg-dark-wood font-sans">
      <main className="relative grid grid-cols-6 gap-1 flex-1 w-full max-w-4xl py-16 px-12">
        <PaperBorder />
        <div className="col-span-6 flex flex-col items-center gap-5">
          <h1 className="text-masthead text-3xl">The Civic Lantern</h1>
          <MastheadRule>
            <Gavel width={40} height={40} />
          </MastheadRule>
        </div>
      </main>
    </div>
  );
}
