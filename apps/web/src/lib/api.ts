import "server-only";

import { redirect } from "next/navigation";

import { env } from "@/lib/env";
import { createClient } from "@/lib/supabase/server";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData; // multipart upload; sent as-is
  tenantId?: string;
};

// Calls the FastAPI backend from the server with the user's access token. The token
// never reaches the browser; the API verifies it and re-checks X-Tenant-Id itself.
export async function api<T>(path: string, { method = "GET", body, form, tenantId }: Options = {}) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) redirect("/login");

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (tenantId) headers["X-Tenant-Id"] = tenantId;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`${env.apiUrl}${path}`, {
      method,
      headers,
      body: form ?? (body === undefined ? undefined : JSON.stringify(body)),
      cache: "no-store",
      signal: AbortSignal.timeout(form ? 60_000 : 15_000),
    });
  } catch {
    throw new ApiError(503, "The service is not reachable. Try again in a moment.");
  }
  if (res.status === 401) redirect("/login");
  if (!res.ok) {
    let message = "Something went wrong.";
    try {
      const payload = (await res.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") message = payload.detail;
    } catch {
      // keep the generic message
    }
    throw new ApiError(res.status, message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export type Role = "owner" | "admin" | "member";

export type Company = {
  id: string;
  name: string;
  type: "freelancer" | "agency";
  role: Role;
  is_internal: boolean;
};

export type Me = {
  id: string;
  email: string;
  companies: Company[];
  platform_admin: { level: "super" | "support"; mfa_verified: boolean } | null;
};

export type Team = {
  members: { user_id: string; email: string; role: Role; joined_at: string }[];
  invitations: {
    id: string;
    email: string;
    role: "admin" | "member";
    expires_at: string;
    created_at: string;
  }[];
};

export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
