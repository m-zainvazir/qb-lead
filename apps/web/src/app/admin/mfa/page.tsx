import Link from "next/link";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { createClient } from "@/lib/supabase/server";
import { MfaForm } from "./mfa-form";

export default function MfaPage() {
  return (
    <>
      <h1 className="text-2xl font-semibold">Authenticator app</h1>
      <Suspense fallback={<Loading />}>
        <Status />
      </Suspense>
    </>
  );
}

async function Status() {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (data?.claims?.aal === "aal2") {
    return (
      <p className="text-sm">
        This session is verified with your authenticator app.{" "}
        <Link href="/admin" className="underline">
          Open the admin pages
        </Link>
      </p>
    );
  }
  return <MfaForm />;
}
