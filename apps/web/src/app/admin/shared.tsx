import Link from "next/link";

import { ApiError } from "@/lib/api";

export type AdminTenant = {
  id: string;
  name: string;
  type: string;
  status: string;
  is_internal: boolean;
  created_at: string;
  member_count: number;
};

export type AdminTenantDetail = AdminTenant & {
  members: {
    user_id: string;
    email: string;
    role: string;
    joined_at: string;
    last_sign_in_at: string | null;
  }[];
};

// What an admin page shows when the API refuses: not an admin, or MFA not verified yet.
export function AdminRefused({ error }: { error: unknown }) {
  const mfa = error instanceof ApiError && error.message.toLowerCase().includes("authenticator");
  return (
    <div role="alert" className="flex flex-col gap-2 rounded-md bg-red-50 p-4 text-sm text-red-800">
      <p>{error instanceof ApiError ? error.message : "Access refused."}</p>
      {mfa && (
        <Link href="/admin/mfa" className="underline">
          Verify with your authenticator app
        </Link>
      )}
    </div>
  );
}
