import { unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { ActionForm, Field } from "@/components/action-form";
import { Loading } from "@/components/loading";
import { api } from "@/lib/api";
import { loadCompany } from "../company";
import { AutoRefresh } from "../profile/auto-refresh";
import { deletePortfolio, downloadPortfolio, uploadPortfolio } from "./actions";

type Item = {
  id: string;
  title: string;
  mime_type: string;
  size_bytes: number;
  status: "uploaded" | "processing" | "ready" | "failed";
  summary: string | null;
  error: string | null;
  created_at: string;
};

export default function PortfolioPage({ params }: PageProps<"/t/[tenantId]/portfolio">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Portfolio</h1>
      <p className="max-w-xl text-sm text-neutral-600">
        Case studies and past work. We use them to match leads and to write proposals. Files stay
        private to your company.
      </p>
      <Suspense fallback={<Loading label="Loading your portfolio…" />}>
        <Items params={params} />
      </Suspense>
    </>
  );
}

async function Items({ params }: Pick<PageProps<"/t/[tenantId]/portfolio">, "params">) {
  const { tenantId } = await params;
  const { company } = await loadCompany(tenantId);
  const canEdit = company.role !== "member";
  let items: Item[];
  try {
    items = await api<Item[]>("/portfolio", { tenantId });
  } catch (err) {
    unstable_rethrow(err);
    return (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
        Could not load the portfolio. Reload to try again.
      </p>
    );
  }
  const busy = items.some((i) => i.status === "uploaded" || i.status === "processing");
  return (
    <>
      {busy && <AutoRefresh seconds={3} />}
      {canEdit && (
        <section className="max-w-sm">
          <ActionForm action={uploadPortfolio.bind(null, tenantId)} submitLabel="Upload">
            <Field name="title" label="Title (optional)" required={false} maxLength={200} />
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium">File (PDF, Word or text, up to 10 MB)</span>
              <input
                name="file"
                type="file"
                required
                accept=".pdf,.docx,.txt,.md,application/pdf,text/plain"
              />
            </label>
          </ActionForm>
        </section>
      )}
      {items.length === 0 ? (
        <p className="rounded-md border border-dashed p-6 text-sm text-neutral-500">
          No portfolio items yet.
        </p>
      ) : (
        <ul className="flex flex-col divide-y rounded-md border">
          {items.map((i) => (
            <li key={i.id} className="flex flex-col gap-1 p-4 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{i.title}</span>
                <span className="flex items-center gap-3">
                  <span className="text-xs text-neutral-500">
                    {i.status === "ready"
                      ? "Ready"
                      : i.status === "failed"
                        ? "Could not read"
                        : "Reading…"}
                  </span>
                  <form action={downloadPortfolio}>
                    <input type="hidden" name="tenantId" value={tenantId} />
                    <input type="hidden" name="itemId" value={i.id} />
                    <button className="underline">Download</button>
                  </form>
                  {canEdit && (
                    <form action={deletePortfolio}>
                      <input type="hidden" name="tenantId" value={tenantId} />
                      <input type="hidden" name="itemId" value={i.id} />
                      <button className="text-red-700 underline">Delete</button>
                    </form>
                  )}
                </span>
              </div>
              {i.summary && <p className="text-neutral-600">{i.summary}</p>}
              {i.error && <p className="text-red-700">{i.error}</p>}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
