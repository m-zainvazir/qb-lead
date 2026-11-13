import { ActionForm, Field } from "@/components/action-form";
import { updatePassword } from "../actions";

// Reached from the email link: /auth/confirm signs the user in with a recovery session first.
export default function ResetPasswordPage() {
  return (
    <>
      <h1 className="text-2xl font-semibold">Choose a new password</h1>
      <p className="text-sm text-neutral-600">
        Changing your password signs you out everywhere else.
      </p>
      <ActionForm action={updatePassword} submitLabel="Change password">
        <Field
          name="password"
          label="New password"
          type="password"
          autoComplete="new-password"
          minLength={10}
          maxLength={128}
        />
        <Field
          name="confirm"
          label="Repeat new password"
          type="password"
          autoComplete="new-password"
          minLength={10}
          maxLength={128}
        />
      </ActionForm>
    </>
  );
}
