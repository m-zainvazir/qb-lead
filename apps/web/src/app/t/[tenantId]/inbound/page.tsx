import { unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { api } from "@/lib/api";
import { loadCompany } from "../company";
import { revokeEndpoint, sendTest } from "./actions";
import { CreateEndpoint } from "./create-endpoint";

type Inbound = {
  endpoints: {
    id: string;
    kind: "webhook" | "email";
    token_hint: string;
    email: string | null;
    created_at: string;
  }[];
  items: {
    id: string;
    source_key: string;
    title: string | null;
    body: string | null;
    url: string | null;
    author_handle: string | null;
    fetched_at: string;
  }[];
};

const fmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export default function InboundPage({ params }: PageProps<"/t/[tenantId]/inbound">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Inbound</h1>
      <p className="max-w-xl text-sm text-neutral-600">
        Send your own leads in: website forms, n8n flows, or forwarded job alert emails. They stay
        private to your company.
      </p>
      <Suspense fallback={<Loading />}>
        <InboundView params={params} />
      </Suspense>
    </>
  );
}

async function InboundView({ params }: Pick<PageProps<"/t/[tenantId]/inbound">, "params">) {
  const { tenantId } = await params;
  const { company } = await loadCompany(tenantId);
  const canEdit = company.role !== "member";
  let data: Inbound;
  try {
    data = await api<Inbound>("/inbound", { tenantId });
  } catch (err) {
    unstable_rethrow(err);
    return (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
        Could not load your inbound addresses. Reload to try again.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-8">
      {canEdit && (
        <section className="flex flex-col gap-3">
          <h2 className="font-semibold">Your addresses</h2>
          {data.endpoints.length === 0 ? (
            <p className="text-sm text-neutral-500">No addresses yet.</p>
          ) : (
            <ul className="divide-y rounded-md border text-sm">
              {data.endpoints.map((e) => (
                <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                  <span>
                    {e.kind === "webhook" ? `Webhook …/ingest/${e.token_hint}…` : e.email}
                    <span className="ml-2 text-xs text-neutral-500">
                      since {fmt.format(new Date(e.created_at))}
                    </span>
                  </span>
                  <form action={revokeEndpoint}>
                    <input type="hidden" name="tenantId" value={tenantId} />
                    <input type="hidden" name="id" value={e.id} />
                    <button className="text-red-700 underline">Revoke</button>
                  </form>
                </li>
              ))}
            </ul>
          )}
          <CreateEndpoint tenantId={tenantId} />
          <form action={sendTest}>
            <input type="hidden" name="tenantId" value={tenantId} />
            <button className="rounded-md border px-4 py-2 text-sm">Send test</button>
          </form>
        </section>
      )}

      <section>
        <h2 className="mb-2 font-semibold">Received ({data.items.length})</h2>
        {data.items.length === 0 ? (
          <p className="rounded-md border border-dashed p-6 text-sm text-neutral-500">
            Nothing received yet.
          </p>
        ) : (
          <ul className="divide-y rounded-md border text-sm">
            {data.items.map((i) => (
              <li key={i.id} className="flex flex-col gap-1 p-3">
                <span className="text-xs text-neutral-500">
                  {i.source_key} · {fmt.format(new Date(i.fetched_at))} · private to your company
                </span>
                {/* Outside content is always shown as plain text (React escapes it). */}
                <span className="font-medium">{i.title ?? "(no title)"}</span>
                {i.body && <span className="whitespace-pre-line text-neutral-600">{i.body}</span>}
                {i.url && <span className="break-all text-xs text-neutral-500">{i.url}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
