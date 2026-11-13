import Link from "next/link";
import { Suspense } from "react";

import { ActionForm, Field } from "@/components/action-form";
import { Loading } from "@/components/loading";
import { signUp } from "../actions";

export default function SignupPage({ searchParams }: PageProps<"/signup">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Create an account</h1>
      <Suspense fallback={<Loading />}>
        <SignupForm searchParams={searchParams} />
      </Suspense>
      <p className="text-sm">
        Already have an account?{" "}
        <Link href="/login" className="underline">
          Sign in
        </Link>
      </p>
    </>
  );
}

async function SignupForm({ searchParams }: Pick<PageProps<"/signup">, "searchParams">) {
  const { next } = await searchParams;
  return (
    <ActionForm action={signUp} submitLabel="Sign up" hideOnSuccess>
      <input type="hidden" name="next" value={typeof next === "string" ? next : ""} />
      <Field name="email" label="Email" type="email" autoComplete="email" maxLength={320} />
      <Field
        name="password"
        label="Password (10+ characters, upper and lower case, a digit)"
        type="password"
        autoComplete="new-password"
        minLength={10}
        maxLength={128}
      />
    </ActionForm>
  );
}
