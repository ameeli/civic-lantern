import Gavel from "@/components/Gavel";
import PaperBorder from "@/components/PaperBorder";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center py-5 bg-dark-wood font-sans dark:bg-black">
      <main className="relative grid grid-cols-6 gap-1 flex-1 w-full max-w-4xl py-16 px-12">
        <PaperBorder />
        <div className="col-span-6 flex flex-col items-center gap-4">
          <h1 className="text-masthead text-3xl">The Civic Lantern</h1>
          <Gavel width={40} height={40} />
        </div>
      </main>
    </div>
  );
}
