import Link from "next/link";

import { ActionForm, Field } from "@/components/action-form";
import { requestPasswordReset } from "../actions";

export default function ForgotPasswordPage() {
  return (
    <>
      <h1 className="text-2xl font-semibold">Reset your password</h1>
      <ActionForm action={requestPasswordReset} submitLabel="Send reset link" hideOnSuccess>
        <Field name="email" label="Email" type="email" autoComplete="email" maxLength={320} />
      </ActionForm>
      <Link href="/login" className="text-sm underline">
        Back to sign in
      </Link>
    </>
  );
}
