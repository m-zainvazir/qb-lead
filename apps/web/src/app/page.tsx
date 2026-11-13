import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 px-4 py-16">
      <h1 className="text-2xl font-semibold">Lead Generation</h1>
      <p className="text-sm text-neutral-600">Sign in to see the leads matched to your company.</p>
      <Link
        href="/login"
        className="rounded-md bg-neutral-900 px-4 py-2 text-center text-sm font-medium text-white"
      >
        Sign in
      </Link>
    </main>
  );
}
