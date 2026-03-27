import Image from "next/image";

export default function Home() {
  return (
    <div className="relative flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-1 w-full max-w-3xl flex-col items-center justify-between py-32 px-16 bg-white dark:bg-black sm:items-start">
        <img
          src="/weathered-paper.svg"
          aria-hidden="true"
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
        />
        <div className="relative z-10 flex"></div>
      </main>
    </div>
  );
}
