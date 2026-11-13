"use server";

import { redirect, unstable_rethrow } from "next/navigation";

import type { FormState } from "@/components/action-form";
import { api, ApiError } from "@/lib/api";

export async function createCompany(_state: FormState, formData: FormData): Promise<FormState> {
  const name = String(formData.get("name") ?? "").trim();
  const type = String(formData.get("type") ?? "");
  if (name.length < 1 || name.length > 120) return { error: "Use a name of 1 to 120 characters." };
  if (type !== "agency" && type !== "freelancer") return { error: "Choose agency or freelancer." };

  let id: string;
  try {
    ({ id } = await api<{ id: string }>("/tenants", { method: "POST", body: { name, type } }));
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && err.status === 409) {
      return { error: "You have reached the limit of companies you can own." };
    }
    return { error: err instanceof ApiError ? err.message : "Could not create the company." };
  }
  redirect(`/switch/${id}`);
}
