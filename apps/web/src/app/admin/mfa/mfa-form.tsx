"use client";

import { useActionState } from "react";

import { mfaAction, type EnrollState } from "./actions";

export function MfaForm() {
  const [state, action, pending] = useActionState<EnrollState, FormData>(mfaAction, {
    step: "start",
  });
  return (
    <form action={action} className="flex max-w-sm flex-col gap-4">
      {state.step === "start" ? (
        <p className="text-sm text-neutral-600">
          Admin pages need a second step at sign-in. Use any authenticator app (1Password, Google
          Authenticator, Authy…).
        </p>
      ) : (
        <>
          {state.qr && (
            <div className="flex flex-col gap-2 text-sm">
              <p>Scan this code with your authenticator app:</p>
              {/* eslint-disable-next-line @next/next/no-img-element -- data URL from Supabase */}
              <img src={state.qr} alt="Authenticator QR code" width={180} height={180} />
              <p className="text-neutral-600">
                Or enter this key: <code className="break-all">{state.secret}</code>
              </p>
            </div>
          )}
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">6-digit code</span>
            <input
              name="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9 ]{6,7}"
              required
              className="rounded-md border border-neutral-300 px-3 py-2"
            />
          </label>
        </>
      )}
      {state.error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {pending ? "Working…" : state.step === "start" ? "Continue" : "Verify"}
      </button>
    </form>
  );
}
