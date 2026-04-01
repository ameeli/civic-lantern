import PaperBorder from "@/components/PaperBorder";

export default function Home() {
  return (
    <div className="relative flex flex-col flex-1 items-center justify-center py-5 bg-dark-wood font-sans dark:bg-black">
      <main className="relative flex flex-1 w-full max-w-5xl flex-col items-center justify-between py-16 px-12 sm:items-start">
        <PaperBorder />
        <div className="relative z-10 flex w-full justify-center">
          <h1 className="text-masthead text-3xl">The Civic Lantern</h1>
        </div>
      </main>
    </div>
  );
}
