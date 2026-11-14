"use server";

import { revalidatePath } from "next/cache";
import { unstable_rethrow } from "next/navigation";

import { api, ApiError } from "@/lib/api";

const KEY = /^[a-z][a-z0-9_]{1,40}$/;

export async function runNow(formData: FormData): Promise<void> {
  const key = String(formData.get("key") ?? "");
  if (!KEY.test(key)) return;
  try {
    await api(`/admin/sources/${key}/run`, { method: "POST" });
  } catch (err) {
    unstable_rethrow(err);
  }
  revalidatePath("/admin/sources");
}

export async function changeSource(formData: FormData): Promise<void> {
  const key = String(formData.get("key") ?? "");
  if (!KEY.test(key)) return;
  const body: Record<string, unknown> = {};
  const enabled = formData.get("enabled");
  if (enabled === "true" || enabled === "false") body.enabled = enabled === "true";
  const cap = formData.get("monthly_cap_usd");
  if (typeof cap === "string" && cap.trim() !== "" && Number.isFinite(Number(cap))) {
    body.monthly_cap_usd = Number(cap);
  }
  if (formData.get("red_override") === "true") body.red_override = true;
  try {
    await api(`/admin/sources/${key}`, { method: "PATCH", body });
  } catch (err) {
    unstable_rethrow(err);
    if (!(err instanceof ApiError)) throw err;
  }
  revalidatePath("/admin/sources");
}
