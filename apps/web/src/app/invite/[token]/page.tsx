import Link from "next/link";
import { unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { ActionForm } from "@/components/action-form";
import { Loading } from "@/components/loading";
import { api, ApiError } from "@/lib/api";
import { createClient } from "@/lib/supabase/server";
import { acceptInvitation } from "./actions";

type Preview = { company_name: string; role: string; email: string; is_valid: boolean };

export default function InvitePage({ params }: PageProps<"/invite/[token]">) {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 px-4 py-16">
      <h1 className="text-2xl font-semibold">Team invitation</h1>
      <Suspense fallback={<Loading />}>
        <Invitation params={params} />
      </Suspense>
    </main>
  );
}

async function Invitation({ params }: Pick<PageProps<"/invite/[token]">, "params">) {
  const { token } = await params;
  if (!/^[A-Za-z0-9_-]{20,200}$/.test(token)) return <Invalid />;

  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  const next = encodeURIComponent(`/invite/${token}`);
  if (!data?.claims) {
    return (
      <>
        <p className="text-sm text-neutral-600">
          Sign in, or create an account with the email address the invitation was sent to.
        </p>
        <div className="flex gap-4 text-sm">
          <Link href={`/login?next=${next}`} className="underline">
            Sign in
          </Link>
          <Link href={`/signup?next=${next}`} className="underline">
            Create an account
          </Link>
        </div>
      </>
    );
  }

  let preview: Preview;
  try {
    preview = await api<Preview>("/invitations/preview", { method: "POST", body: { token } });
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && (err.status === 404 || err.status === 422)) return <Invalid />;
    throw err;
  }
  if (!preview.is_valid) return <Invalid />;

  const signedInAs = String(data.claims.email ?? "");
  if (signedInAs.toLowerCase() !== preview.email.toLowerCase()) {
    return (
      <p role="alert" className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
        This invitation was sent to a different email address than the one you are signed in with (
        {signedInAs}). Sign out and sign in with the invited address.
      </p>
    );
  }
  return (
    <>
      <p className="text-sm">
        Join <strong>{preview.company_name}</strong> as <strong>{preview.role}</strong>.
      </p>
      <ActionForm action={acceptInvitation.bind(null, token)} submitLabel="Accept invitation">
        {null}
      </ActionForm>
    </>
  );
}

function Invalid() {
  return (
    <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
      This invitation link is not valid. It may have been used already, revoked or expired. Ask for
      a new invitation.
    </p>
  );
}
