import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { api, type Me } from "@/lib/api";
import { signOut } from "../(auth)/actions";

// Signed-in entry point: goes to the last company used, the only company, or a picker.
export default function AppHome({ searchParams }: PageProps<"/app">) {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-16">
      <h1 className="text-2xl font-semibold">Your companies</h1>
      <Suspense fallback={<Loading />}>
        <Picker searchParams={searchParams} />
      </Suspense>
    </main>
  );
}

async function Picker({ searchParams }: Pick<PageProps<"/app">, "searchParams">) {
  const { notice, pick } = await searchParams;
  const me = await api<Me>("/me");
  if (me.companies.length === 0) redirect("/onboarding/company");

  const last = (await cookies()).get("last_tenant")?.value;
  if (!pick && notice !== "password-changed") {
    if (last && me.companies.some((c) => c.id === last)) redirect(`/t/${last}`);
    if (me.companies.length === 1) redirect(`/t/${me.companies[0].id}`);
  }

  return (
    <>
      {notice === "password-changed" && (
        <p role="status" className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          Password changed. Other sessions were signed out.
        </p>
      )}
      <p className="text-sm text-neutral-600">Signed in as {me.email}</p>
      <ul className="divide-y rounded-md border">
        {me.companies.map((c) => (
          <li key={c.id} className="flex items-center justify-between p-3">
            <span>
              <span className="font-medium">{c.name}</span>{" "}
              <span className="text-sm text-neutral-500">({c.role})</span>
            </span>
            <a href={`/switch/${c.id}`} className="text-sm underline">
              Open
            </a>
          </li>
        ))}
      </ul>
      <div className="flex gap-4 text-sm">
        <Link href="/onboarding/company" className="underline">
          Create another company
        </Link>
        {me.platform_admin && (
          <Link href="/admin" className="underline">
            Platform admin
          </Link>
        )}
      </div>
      <form action={signOut}>
        <button className="rounded-md border px-4 py-2 text-sm">Sign out everywhere</button>
      </form>
    </>
  );
}
