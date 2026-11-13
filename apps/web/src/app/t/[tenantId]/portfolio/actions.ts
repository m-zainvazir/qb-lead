"use server";

import { revalidatePath } from "next/cache";
import { redirect, unstable_rethrow } from "next/navigation";

import type { FormState } from "@/components/action-form";
import { api, ApiError, UUID_RE } from "@/lib/api";

const MESSAGES: Record<number, string> = {
  413: "Files are limited to 10 MB.",
  415: "Upload a PDF, Word (.docx) or text file. The file's content must match its name.",
};

export async function uploadPortfolio(
  tenantId: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  if (!UUID_RE.test(tenantId)) return { error: "Invalid company." };
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "Choose a file to upload." };
  if (file.size > 10 * 1024 * 1024) return { error: MESSAGES[413] };
  const form = new FormData();
  form.set("file", file, file.name);
  const title = String(formData.get("title") ?? "").trim();
  if (title) form.set("title", title.slice(0, 200));
  try {
    await api("/portfolio", { method: "POST", tenantId, form });
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError) return { error: MESSAGES[err.status] ?? err.message };
    return { error: "Could not upload the file." };
  }
  revalidatePath(`/t/${tenantId}/portfolio`);
  return { message: "Uploaded. We are reading it now; the summary appears in a moment." };
}

export async function deletePortfolio(formData: FormData): Promise<void> {
  const tenantId = String(formData.get("tenantId") ?? "");
  const itemId = String(formData.get("itemId") ?? "");
  if (!UUID_RE.test(tenantId) || !UUID_RE.test(itemId)) return;
  try {
    await api(`/portfolio/${itemId}`, { method: "DELETE", tenantId });
  } catch (err) {
    unstable_rethrow(err);
  }
  revalidatePath(`/t/${tenantId}/portfolio`);
}

export async function downloadPortfolio(formData: FormData): Promise<void> {
  const tenantId = String(formData.get("tenantId") ?? "");
  const itemId = String(formData.get("itemId") ?? "");
  if (!UUID_RE.test(tenantId) || !UUID_RE.test(itemId)) return;
  const { url } = await api<{ url: string }>(`/portfolio/${itemId}/download`, { tenantId });
  redirect(url); // a signed link that expires in 60 seconds
}
