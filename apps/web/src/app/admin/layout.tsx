import Link from "next/link";

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b bg-neutral-900 text-white">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-6 px-4 py-3 text-sm">
          <span className="font-semibold">Platform admin</span>
          <Link href="/admin" className="underline">
            Companies
          </Link>
          <Link href="/admin/mfa" className="underline">
            Authenticator
          </Link>
          <Link href="/app?pick=1" className="ml-auto underline">
            Back to app
          </Link>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-8">
        <p className="rounded-md bg-amber-50 p-3 text-xs text-amber-900">
          Every company you open here is recorded in the audit log with your name and the time.
        </p>
        {children}
      </main>
    </div>
  );
}
