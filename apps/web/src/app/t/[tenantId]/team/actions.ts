"use server";

import { revalidatePath } from "next/cache";
import { redirect, unstable_rethrow } from "next/navigation";

import type { FormState } from "@/components/action-form";
import { api, ApiError, UUID_RE } from "@/lib/api";

function ids(...values: unknown[]): string[] {
  const out = values.map((v) => String(v ?? ""));
  if (!out.every((v) => UUID_RE.test(v))) throw new ApiError(400, "Invalid request.");
  return out;
}

function message(err: unknown): string {
  return err instanceof ApiError ? err.message : "Something went wrong.";
}

export async function inviteMember(
  tenantId: string,
  _state: FormState,
  formData: FormData,
): Promise<FormState> {
  const email = String(formData.get("email") ?? "").trim();
  const role = String(formData.get("role") ?? "member");
  try {
    ids(tenantId);
    const res = await api<{ email_sent: boolean; invite_url: string | null }>("/invitations", {
      method: "POST",
      tenantId,
      body: { email, role },
    });
    revalidatePath(`/t/${tenantId}/team`);
    return res.email_sent
      ? { message: `Invitation sent to ${email}.` }
      : {
          message: `The email could not be sent. Share this link with ${email}: ${res.invite_url}`,
        };
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && err.status === 422)
      return { error: "Enter a valid email address." };
    return { error: message(err) };
  }
}

export async function changeRole(formData: FormData): Promise<void> {
  const [tenantId, userId] = ids(formData.get("tenantId"), formData.get("userId"));
  const role = String(formData.get("role") ?? "");
  try {
    await api(`/team/members/${userId}`, { method: "PATCH", tenantId, body: { role } });
  } catch (err) {
    unstable_rethrow(err);
    redirect(`/t/${tenantId}/team?error=${encodeURIComponent(message(err))}`);
  }
  revalidatePath(`/t/${tenantId}/team`);
}

export async function removeMember(formData: FormData): Promise<void> {
  const [tenantId, userId] = ids(formData.get("tenantId"), formData.get("userId"));
  try {
    await api(`/team/members/${userId}`, { method: "DELETE", tenantId });
  } catch (err) {
    unstable_rethrow(err);
    redirect(`/t/${tenantId}/team?error=${encodeURIComponent(message(err))}`);
  }
  revalidatePath(`/t/${tenantId}/team`);
}

export async function revokeInvitation(formData: FormData): Promise<void> {
  const [tenantId, invitationId] = ids(formData.get("tenantId"), formData.get("invitationId"));
  try {
    await api(`/invitations/${invitationId}`, { method: "DELETE", tenantId });
  } catch (err) {
    unstable_rethrow(err);
    redirect(`/t/${tenantId}/team?error=${encodeURIComponent(message(err))}`);
  }
  revalidatePath(`/t/${tenantId}/team`);
}
