"use server";

import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

export type EnrollState =
  | { step: "start"; error?: string }
  | { step: "code"; factorId: string; qr?: string; secret?: string; error?: string };

// Step 1: reuse a verified authenticator, or enroll a new one (QR code + secret).
export async function startMfa(): Promise<EnrollState> {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.mfa.listFactors();
  if (error) return { step: "start", error: "Could not load your authenticators. Sign in again." };

  const verified = data.totp.find((f) => f.status === "verified");
  if (verified) return { step: "code", factorId: verified.id };

  // Drop half-finished enrolments so a fresh QR code can be shown.
  for (const f of data.all.filter((f) => f.factor_type === "totp" && f.status !== "verified")) {
    await supabase.auth.mfa.unenroll({ factorId: f.id });
  }
  const enrolled = await supabase.auth.mfa.enroll({
    factorType: "totp",
    friendlyName: `Authenticator ${new Date().toISOString().slice(0, 10)}`,
  });
  if (enrolled.error) return { step: "start", error: "Could not start enrolment. Try again." };
  return {
    step: "code",
    factorId: enrolled.data.id,
    qr: enrolled.data.totp.qr_code,
    secret: enrolled.data.totp.secret,
  };
}

// Step 2: verify a 6-digit code. Success upgrades the session to aal2 (cookie updated).
export async function verifyMfa(state: EnrollState, formData: FormData): Promise<EnrollState> {
  if (state.step !== "code") return { step: "start" };
  const code = String(formData.get("code") ?? "").replace(/\s/g, "");
  if (!/^\d{6}$/.test(code)) return { ...state, error: "Enter the 6-digit code from your app." };

  const supabase = await createClient();
  const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId: state.factorId, code });
  if (error)
    return { ...state, error: "That code did not work. Wait for a new one and try again." };
  redirect("/admin");
}

export async function mfaAction(state: EnrollState, formData: FormData): Promise<EnrollState> {
  return state.step === "start" ? startMfa() : verifyMfa(state, formData);
}
