"use server";

import { redirect, unstable_rethrow } from "next/navigation";

import type { FormState } from "@/components/action-form";
import { api, ApiError } from "@/lib/api";

export async function acceptInvitation(token: string): Promise<FormState> {
  let tenantId: string;
  try {
    ({ tenant_id: tenantId } = await api<{ tenant_id: string }>("/invitations/accept", {
      method: "POST",
      body: { token },
    }));
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && err.status === 404) {
      return {
        error:
          "This invitation is not valid for your account. It may have been used, revoked or expired, or it was sent to a different email address.",
      };
    }
    return { error: "Could not accept the invitation. Try again." };
  }
  redirect(`/switch/${tenantId}`);
}
