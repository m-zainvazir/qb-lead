import { redirect } from "next/navigation";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "../(auth)/actions";

// Signed-in home. Module 1 step 10 turns this into the company picker.
export default function AppHome({ searchParams }: PageProps<"/app">) {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-16">
      <h1 className="text-2xl font-semibold">Your account</h1>
      <Suspense fallback={<Loading />}>
        <Account searchParams={searchParams} />
      </Suspense>
    </main>
  );
}

async function Account({ searchParams }: Pick<PageProps<"/app">, "searchParams">) {
  const { notice } = await searchParams;
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims) redirect("/login");
  return (
    <>
      {notice === "password-changed" && (
        <p role="status" className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          Password changed. Other sessions were signed out.
        </p>
      )}
      <p className="text-sm text-neutral-600">{String(data.claims.email ?? "")}</p>
      <form action={signOut}>
        <button className="rounded-md border px-4 py-2 text-sm">Sign out everywhere</button>
      </form>
    </>
  );
}
