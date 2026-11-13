import Link from "next/link";
import { unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { api } from "@/lib/api";
import { AdminRefused, type AdminTenant } from "./shared";

const PAGE = 50;

export default function AdminHome({ searchParams }: PageProps<"/admin">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Companies</h1>
      <Suspense fallback={<Loading />}>
        <TenantList searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function TenantList({ searchParams }: Pick<PageProps<"/admin">, "searchParams">) {
  const { page } = await searchParams;
  const n = Math.max(0, Math.min(1000, Number(page) || 0));
  let data: { items: AdminTenant[] };
  try {
    data = await api(`/admin/tenants?limit=${PAGE}&offset=${n * PAGE}`);
  } catch (err) {
    unstable_rethrow(err);
    return <AdminRefused error={err} />;
  }
  if (data.items.length === 0) return <p className="text-sm text-neutral-500">No companies.</p>;
  return (
    <>
      <table className="w-full text-left text-sm">
        <thead className="border-b text-neutral-500">
          <tr>
            <th className="py-2">Name</th>
            <th>Type</th>
            <th>Status</th>
            <th>Members</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {data.items.map((t) => (
            <tr key={t.id}>
              <td className="py-2">
                <Link href={`/admin/tenants/${t.id}`} className="underline">
                  {t.name}
                </Link>
                {t.is_internal && <span className="ml-2 text-xs text-neutral-500">internal</span>}
              </td>
              <td>{t.type}</td>
              <td>{t.status}</td>
              <td>{t.member_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-4 text-sm">
        {n > 0 && (
          <Link href={`/admin?page=${n - 1}`} className="underline">
            Previous
          </Link>
        )}
        {data.items.length === PAGE && (
          <Link href={`/admin?page=${n + 1}`} className="underline">
            Next
          </Link>
        )}
      </div>
    </>
  );
}
