import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { signOut } from "../../(auth)/actions";
import { loadCompany } from "./company";

export default function CompanyLayout({ children, params }: LayoutProps<"/t/[tenantId]">) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b">
        <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Suspense fallback={<Loading />}>
            <Nav params={params} />
          </Suspense>
          <form action={signOut}>
            <button className="text-sm underline">Sign out</button>
          </form>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8">
        {children}
      </main>
    </div>
  );
}

async function Nav({ params }: Pick<LayoutProps<"/t/[tenantId]">, "params">) {
  const { tenantId } = await params;
  const { me, company } = await loadCompany(tenantId);
  const others = me.companies.filter((c) => c.id !== company.id);
  return (
    <nav className="flex flex-wrap items-center gap-4 text-sm">
      <span className="font-semibold">{company.name}</span>
      <Link href={`/t/${company.id}`} className="underline">
        Home
      </Link>
      <Link href={`/t/${company.id}/profile`} className="underline">
        Profile
      </Link>
      <Link href={`/t/${company.id}/portfolio`} className="underline">
        Portfolio
      </Link>
      <Link href={`/t/${company.id}/inbound`} className="underline">
        Inbound
      </Link>
      {company.role !== "member" && (
        <Link href={`/t/${company.id}/team`} className="underline">
          Team
        </Link>
      )}
      {others.length > 0 && (
        <details className="relative">
          <summary className="cursor-pointer underline">Switch company</summary>
          <ul className="absolute z-10 mt-2 min-w-48 rounded-md border bg-white p-2 shadow">
            {others.map((c) => (
              <li key={c.id}>
                <a
                  href={`/switch/${c.id}`}
                  className="block rounded px-2 py-1 hover:bg-neutral-100"
                >
                  {c.name}
                </a>
              </li>
            ))}
            <li>
              <Link
                href="/onboarding/company"
                className="block rounded px-2 py-1 hover:bg-neutral-100"
              >
                + New company
              </Link>
            </li>
          </ul>
        </details>
      )}
      {me.platform_admin && (
        <Link href="/admin" className="underline">
          Admin
        </Link>
      )}
    </nav>
  );
}
