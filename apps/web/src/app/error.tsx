"use client";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 px-4 py-16">
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p className="text-sm text-neutral-600">
        The request failed. It may be a slow or broken connection. Try again in a moment.
      </p>
      <button onClick={reset} className="self-start rounded-md border px-4 py-2 text-sm">
        Try again
      </button>
    </main>
  );
}
