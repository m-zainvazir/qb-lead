"use server";

import { redirect } from "next/navigation";

import type { FormState } from "@/components/action-form";
import { env } from "@/lib/env";
import { safeNext } from "@/lib/redirects";
import { createClient } from "@/lib/supabase/server";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function readEmail(formData: FormData): string | null {
  const email = String(formData.get("email") ?? "")
    .trim()
    .toLowerCase();
  return email.length <= 320 && EMAIL.test(email) ? email : null;
}

function readPassword(formData: FormData, field = "password"): string {
  return String(formData.get(field) ?? "");
}

// Messages never reveal whether an account exists for an email address.
const CHECK_EMAIL =
  "If that address can be used, we have sent an email with a link. Check your inbox.";

export async function signUp(_state: FormState, formData: FormData): Promise<FormState> {
  const email = readEmail(formData);
  const password = readPassword(formData);
  const next = safeNext(String(formData.get("next") ?? ""), "/app");
  if (!email) return { error: "Enter a valid email address." };
  if (password.length < 10 || password.length > 128) {
    return { error: "Use a password of 10 to 128 characters." };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signUp({
    email,
    password,
    options: { emailRedirectTo: `${env.webBaseUrl}${next}` },
  });
  if (error) {
    if (error.code === "weak_password") {
      return {
        error:
          "That password is too weak. Use upper and lower case letters and digits, and avoid common passwords.",
      };
    }
    if (error.status === 429) return { error: "Too many attempts. Wait a few minutes." };
    // Anything else (including "already registered") gets the same answer as success.
  }
  return { message: CHECK_EMAIL };
}

export async function signIn(_state: FormState, formData: FormData): Promise<FormState> {
  const email = readEmail(formData);
  const password = readPassword(formData);
  const next = safeNext(String(formData.get("next") ?? ""), "/app");
  if (!email || !password) return { error: "Email or password is incorrect." };

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    if (error.status === 429) return { error: "Too many attempts. Wait a few minutes." };
    if (error.code === "email_not_confirmed") {
      // Only reachable with the correct password, so it reveals nothing new.
      return { error: "Confirm your email first. We sent you a link when you signed up." };
    }
    return { error: "Email or password is incorrect." };
  }
  redirect(next);
}

export async function requestPasswordReset(
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const email = readEmail(formData);
  if (!email) return { error: "Enter a valid email address." };
  const supabase = await createClient();
  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${env.webBaseUrl}/reset-password`,
  });
  if (error?.status === 429) return { error: "Too many attempts. Wait a few minutes." };
  return { message: CHECK_EMAIL };
}

export async function updatePassword(_state: FormState, formData: FormData): Promise<FormState> {
  const password = readPassword(formData);
  const confirm = readPassword(formData, "confirm");
  if (password !== confirm) return { error: "The two passwords do not match." };
  if (password.length < 10 || password.length > 128) {
    return { error: "Use a password of 10 to 128 characters." };
  }
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims?.sub) return { error: "Your reset link has expired. Ask for a new one." };

  const { error } = await supabase.auth.updateUser({ password });
  if (error) {
    if (error.code === "weak_password") {
      return { error: "That password is too weak. Use upper and lower case letters and digits." };
    }
    if (error.code === "same_password") return { error: "Choose a password you have not used." };
    return { error: "Could not change the password. Ask for a new reset link." };
  }
  // A password change ends every other session (other browsers, stolen cookies).
  await supabase.auth.signOut({ scope: "others" });
  redirect("/app?notice=password-changed");
}

export async function signOut(): Promise<void> {
  const supabase = await createClient();
  // Global: signing out ends every session of this user, on every device.
  await supabase.auth.signOut({ scope: "global" });
  redirect("/login");
}
