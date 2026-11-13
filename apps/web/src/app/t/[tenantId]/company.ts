import "server-only";

import { notFound } from "next/navigation";
import { cache } from "react";

import { api, UUID_RE, type Company, type Me } from "@/lib/api";

// The company in the URL, but only if the signed-in user belongs to it. Anything
// else is "not found", so another company's address reveals nothing.
export const loadCompany = cache(
  async (tenantId: string): Promise<{ me: Me; company: Company }> => {
    if (!UUID_RE.test(tenantId)) notFound();
    const me = await api<Me>("/me");
    const company = me.companies.find((c) => c.id === tenantId);
    if (!company) notFound();
    return { me, company };
  },
);
