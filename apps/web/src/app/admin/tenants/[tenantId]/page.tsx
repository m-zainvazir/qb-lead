import { notFound, unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { api, ApiError, UUID_RE } from "@/lib/api";
import { AdminRefused, type AdminTenantDetail } from "../../shared";

const fmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export default function AdminTenantPage({ params }: PageProps<"/admin/tenants/[tenantId]">) {
  return (
    <Suspense fallback={<Loading />}>
      <Detail params={params} />
    </Suspense>
  );
}

async function Detail({ params }: Pick<PageProps<"/admin/tenants/[tenantId]">, "params">) {
  const { tenantId } = await params;
  if (!UUID_RE.test(tenantId)) notFound();
  let t: AdminTenantDetail;
  try {
    t = await api<AdminTenantDetail>(`/admin/tenants/${tenantId}`);
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && err.status === 404) notFound();
    return <AdminRefused error={err} />;
  }
  return (
    <>
      <h1 className="text-2xl font-semibold">{t.name}</h1>
      <p className="text-sm text-neutral-600">
        {t.type} · {t.status} · created {fmt.format(new Date(t.created_at))}
        {t.is_internal && " · internal"}
      </p>
      <h2 className="font-semibold">Members ({t.members.length})</h2>
      <ul className="divide-y rounded-md border text-sm">
        {t.members.map((m) => (
          <li key={m.user_id} className="flex justify-between p-3">
            <span>{m.email}</span>
            <span className="text-neutral-600">
              {m.role} · last sign-in{" "}
              {m.last_sign_in_at ? fmt.format(new Date(m.last_sign_in_at)) : "never"}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}
