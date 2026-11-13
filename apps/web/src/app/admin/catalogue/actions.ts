"use server";

import { revalidatePath } from "next/cache";
import { unstable_rethrow } from "next/navigation";

import type { FormState } from "@/components/action-form";
import { api, ApiError, UUID_RE } from "@/lib/api";

function lines(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

export async function addService(_state: FormState, formData: FormData): Promise<FormState> {
  const name = String(formData.get("name") ?? "").trim();
  const slug =
    String(formData.get("slug") ?? "").trim() ||
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
  // One problem per line: "Problem label | phrase one; phrase two"
  const problems = lines(formData.get("problems")).map((line) => {
    const [label, phrases = ""] = line.split("|");
    return {
      label: label.trim(),
      phrases: phrases
        .split(";")
        .map((p) => p.trim())
        .filter(Boolean),
    };
  });
  try {
    await api("/admin/catalogue/services", {
      method: "POST",
      body: { slug, name, description: String(formData.get("description") ?? ""), problems },
    });
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && err.status === 409)
      return { error: "That slug already exists." };
    if (err instanceof ApiError && err.status === 422) return { error: "Check the name and slug." };
    return { error: err instanceof ApiError ? err.message : "Could not add the service." };
  }
  revalidatePath("/admin/catalogue");
  return { message: `Added ${name}. It is offered in onboarding now.` };
}

export async function setActive(formData: FormData): Promise<void> {
  const kind = String(formData.get("kind") ?? "");
  const id = String(formData.get("id") ?? "");
  const active = formData.get("active") === "true";
  if (!UUID_RE.test(id)) return;
  if (!["services", "markets", "signal_types", "onboarding_questions"].includes(kind)) return;
  try {
    await api(`/admin/catalogue/${kind}/${id}`, { method: "PATCH", body: { is_active: active } });
  } catch (err) {
    unstable_rethrow(err);
  }
  revalidatePath("/admin/catalogue");
}
