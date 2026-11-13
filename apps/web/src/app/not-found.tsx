import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 px-4 py-16">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="text-sm text-neutral-600">
        This page does not exist, or you do not have access to it.
      </p>
      <Link href="/app?pick=1" className="text-sm underline">
        Go to your companies
      </Link>
    </main>
  );
}
