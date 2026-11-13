import Link from "next/link";
import { Suspense } from "react";

import { ActionForm, Field } from "@/components/action-form";
import { Loading } from "@/components/loading";
import { signIn } from "../actions";

export default function LoginPage({ searchParams }: PageProps<"/login">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <Suspense fallback={<Loading />}>
        <LoginForm searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function LoginForm({ searchParams }: Pick<PageProps<"/login">, "searchParams">) {
  const { next } = await searchParams;
  const nextValue = typeof next === "string" ? next : "";
  return (
    <>
      <ActionForm action={signIn} submitLabel="Sign in">
        <input type="hidden" name="next" value={nextValue} />
        <Field name="email" label="Email" type="email" autoComplete="email" maxLength={320} />
        <Field name="password" label="Password" type="password" autoComplete="current-password" />
      </ActionForm>
      <div className="flex justify-between text-sm">
        <Link href="/forgot-password" className="underline">
          Forgot password?
        </Link>
        <Link
          href={nextValue ? `/signup?next=${encodeURIComponent(nextValue)}` : "/signup"}
          className="underline"
        >
          Create an account
        </Link>
      </div>
    </>
  );
}
