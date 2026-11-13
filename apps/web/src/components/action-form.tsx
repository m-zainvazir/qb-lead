"use client";

import { useActionState, type ReactNode } from "react";

export type FormState = { error?: string; message?: string } | null;
export type FormAction = (state: FormState, formData: FormData) => Promise<FormState>;

// A form bound to a server action, with pending, error and success states.
export function ActionForm({
  action,
  submitLabel,
  children,
  hideOnSuccess = false,
}: {
  action: FormAction;
  submitLabel: string;
  children: ReactNode;
  hideOnSuccess?: boolean;
}) {
  const [state, formAction, pending] = useActionState(action, null);
  if (hideOnSuccess && state?.message) {
    return (
      <p role="status" className="rounded-md bg-green-50 p-3 text-sm text-green-800">
        {state.message}
      </p>
    );
  }
  return (
    <form action={formAction} className="flex flex-col gap-4">
      {children}
      {state?.error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {state.error}
        </p>
      )}
      {state?.message && (
        <p role="status" className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          {state.message}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {pending ? "Working…" : submitLabel}
      </button>
    </form>
  );
}

export function Field({
  name,
  label,
  type = "text",
  autoComplete,
  required = true,
  defaultValue,
  minLength,
  maxLength,
}: {
  name: string;
  label: string;
  type?: string;
  autoComplete?: string;
  required?: boolean;
  defaultValue?: string;
  minLength?: number;
  maxLength?: number;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{label}</span>
      <input
        name={name}
        type={type}
        autoComplete={autoComplete}
        required={required}
        defaultValue={defaultValue}
        minLength={minLength}
        maxLength={maxLength}
        className="rounded-md border border-neutral-300 px-3 py-2"
      />
    </label>
  );
}
