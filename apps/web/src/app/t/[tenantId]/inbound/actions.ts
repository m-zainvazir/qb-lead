"use server";

import { revalidatePath } from "next/cache";
import { unstable_rethrow } from "next/navigation";

import { api, ApiError, UUID_RE } from "@/lib/api";
import { env } from "@/lib/env";

export type CreatedEndpoint = { error?: string; url?: string; email?: string } | null;

export async function createEndpoint(
  tenantId: string,
  kind: "webhook" | "email",
): Promise<CreatedEndpoint> {
  if (!UUID_RE.test(tenantId)) return { error: "Invalid company." };
  try {
    const res = await api<{ path?: string; email?: string }>("/inbound/endpoints", {
      method: "POST",
      tenantId,
      body: { kind },
    });
    revalidatePath(`/t/${tenantId}/inbound`);
    if (res.path) return { url: `${env.publicApiUrl}${res.path}` };
    return { email: res.email };
  } catch (err) {
    unstable_rethrow(err);
    return { error: err instanceof ApiError ? err.message : "Could not create the address." };
  }
}

export async function revokeEndpoint(formData: FormData): Promise<void> {
  const tenantId = String(formData.get("tenantId") ?? "");
  const id = String(formData.get("id") ?? "");
  if (!UUID_RE.test(tenantId) || !UUID_RE.test(id)) return;
  try {
    await api(`/inbound/endpoints/${id}`, { method: "DELETE", tenantId });
  } catch (err) {
    unstable_rethrow(err);
  }
  revalidatePath(`/t/${tenantId}/inbound`);
}

export async function sendTest(formData: FormData): Promise<void> {
  const tenantId = String(formData.get("tenantId") ?? "");
  if (!UUID_RE.test(tenantId)) return;
  try {
    await api("/inbound/test", { method: "POST", tenantId });
  } catch (err) {
    unstable_rethrow(err);
  }
  revalidatePath(`/t/${tenantId}/inbound`);
}
