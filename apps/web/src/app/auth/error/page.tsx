import Link from "next/link";

export default function AuthErrorPage() {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 px-4 py-16">
      <h1 className="text-2xl font-semibold">That link did not work</h1>
      <p className="text-sm text-neutral-600">
        It may have expired or been used already. Links work once.
      </p>
      <div className="flex gap-4 text-sm">
        <Link href="/login" className="underline">
          Sign in
        </Link>
        <Link href="/forgot-password" className="underline">
          Get a new reset link
        </Link>
      </div>
    </main>
  );
}
