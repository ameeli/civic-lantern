"use client";

export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <div className="flex flex-col flex-1 items-center justify-center gap-4 bg-dark-wood font-sans text-center p-12">
      <h1 className="font-headline font-semibold text-2xl">
        Something went wrong loading election data.
      </h1>
      <p className="text-body-justify max-w-md">
        {error.digest
          ? `Reference: ${error.digest}`
          : "Please try again in a moment."}
      </p>
      <button
        onClick={() => unstable_retry()}
        className="border-ink-thin px-4 py-2 font-headline text-sm cursor-pointer"
      >
        Try again
      </button>
    </div>
  );
}
