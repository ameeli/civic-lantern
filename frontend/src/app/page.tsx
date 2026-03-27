import PaperBorder from "@/components/PaperBorder";

export default function Home() {
  return (
    <div className="relative flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="relative flex flex-1 w-full max-w-6xl flex-col items-center justify-between py-32 px-16 sm:items-start">
        <PaperBorder />
        <div className="relative z-10 flex"></div>
      </main>
    </div>
  );
}
