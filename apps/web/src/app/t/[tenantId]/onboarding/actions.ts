"use server";

import { redirect, unstable_rethrow } from "next/navigation";

import { api, ApiError, UUID_RE } from "@/lib/api";

export type Answers = Record<string, string | number | string[] | null>;

export async function saveProgress(
  tenantId: string,
  step: number,
  answers: Answers,
): Promise<{ error?: string }> {
  if (!UUID_RE.test(tenantId)) return { error: "Invalid company." };
  try {
    await api("/onboarding/progress", {
      method: "PUT",
      tenantId,
      body: { current_step: step, answers },
    });
    return {};
  } catch (err) {
    unstable_rethrow(err);
    return { error: err instanceof ApiError ? err.message : "Could not save your answers." };
  }
}

export async function finishOnboarding(
  tenantId: string,
  step: number,
  answers: Answers,
): Promise<{ error?: string }> {
  const saved = await saveProgress(tenantId, step, answers);
  if (saved.error) return saved;
  try {
    await api("/onboarding/complete", { method: "POST", tenantId });
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && err.status === 422) {
      return { error: "Some answers are missing or not valid. Check each step." };
    }
    return { error: err instanceof ApiError ? err.message : "Could not finish onboarding." };
  }
  redirect(`/t/${tenantId}/profile`);
}
