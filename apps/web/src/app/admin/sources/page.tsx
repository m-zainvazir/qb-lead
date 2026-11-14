import { unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { api } from "@/lib/api";
import { AutoRefresh } from "../../t/[tenantId]/profile/auto-refresh";
import { AdminRefused } from "../shared";
import { changeSource, runNow } from "./actions";

type Source = {
  key: string;
  name: string;
  kind: "pull" | "push";
  risk: "green" | "amber" | "red";
  enabled: boolean;
  schedule_seconds: number | null;
  monthly_cap_usd: number;
  spent_this_month: number;
  projected_monthly_usd: number;
  last_run_at: string | null;
  last_status: string | null;
  yield: number | null;
};
type Run = {
  id: string;
  source_key: string;
  status: string;
  trigger: string;
  queries: number;
  fetched: number;
  new_items: number;
  cost_usd: number;
  error: string | null;
  started_at: string;
};
type Item = {
  id: string;
  source_key: string;
  visibility: string;
  title: string | null;
  body: string | null;
  url: string | null;
  author_handle: string | null;
  fetched_at: string;
};

const fmt = new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" });
const RISK = {
  green: "bg-green-100 text-green-900",
  amber: "bg-amber-100 text-amber-900",
  red: "bg-red-100 text-red-900",
};

export default function SourcesPage() {
  return (
    <>
      <h1 className="text-2xl font-semibold">Sources (temporary page)</h1>
      <p className="text-sm text-neutral-600">
        Collection only: nothing here is judged yet. Replaced by the admin panel in module 9.
      </p>
      <Suspense fallback={<Loading />}>
        <SourcesView />
      </Suspense>
    </>
  );
}

async function SourcesView() {
  let sources: Source[], runs: Run[], items: Item[];
  try {
    [sources, runs, items] = await Promise.all([
      api<Source[]>("/admin/sources"),
      api<Run[]>("/admin/sources/runs?limit=20"),
      api<Item[]>("/admin/sources/items?limit=30"),
    ]);
  } catch (err) {
    unstable_rethrow(err);
    return <AdminRefused error={err} />;
  }
  const running = runs.some((r) => r.status === "running");
  return (
    <div className="flex flex-col gap-8">
      {running && <AutoRefresh seconds={3} />}
      <section className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-neutral-500">
            <tr>
              <th className="py-2">Source</th>
              <th>Risk</th>
              <th>Last run</th>
              <th>Spent / cap (month)</th>
              <th>Projected</th>
              <th>Yield</th>
              <th></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {sources.map((s) => (
              <tr key={s.key} className="align-top">
                <td className="py-2">
                  <span className="font-medium">{s.name}</span>
                  <span className="block text-xs text-neutral-500">
                    {s.kind === "push"
                      ? "push (webhook/email)"
                      : s.schedule_seconds
                        ? `every ${Math.round(s.schedule_seconds / 60)} min`
                        : "manual"}
                    {" · "}
                    {s.enabled ? "on" : "off"}
                  </span>
                </td>
                <td>
                  <span className={`rounded px-1.5 py-0.5 text-xs ${RISK[s.risk]}`}>{s.risk}</span>
                </td>
                <td className="text-xs">
                  {s.last_run_at ? fmt.format(new Date(s.last_run_at)) : "never"}
                  {s.last_status && <span className="block text-neutral-500">{s.last_status}</span>}
                </td>
                <td className="text-xs">
                  ${s.spent_this_month.toFixed(4)} / ${s.monthly_cap_usd.toFixed(2)}
                  <form action={changeSource} className="mt-1 flex gap-1">
                    <input type="hidden" name="key" value={s.key} />
                    <input
                      name="monthly_cap_usd"
                      type="number"
                      step="0.01"
                      min="0"
                      defaultValue={s.monthly_cap_usd}
                      className="w-20 rounded border px-1"
                      aria-label={`Monthly cap for ${s.name}`}
                    />
                    <button className="underline">Set</button>
                  </form>
                </td>
                <td className="text-xs">${s.projected_monthly_usd.toFixed(2)}</td>
                <td className="text-xs">
                  {s.yield === null ? "–" : `${Math.round(s.yield * 100)}% new`}
                </td>
                <td className="flex flex-col items-start gap-1 text-xs">
                  {s.kind === "pull" && (
                    <form action={runNow}>
                      <input type="hidden" name="key" value={s.key} />
                      <button className="rounded border px-2 py-1">Run now</button>
                    </form>
                  )}
                  <form action={changeSource}>
                    <input type="hidden" name="key" value={s.key} />
                    <input type="hidden" name="enabled" value={s.enabled ? "false" : "true"} />
                    <button className="underline">{s.enabled ? "Disable" : "Enable"}</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Recent runs</h2>
        {runs.length === 0 ? (
          <p className="text-sm text-neutral-500">No runs yet.</p>
        ) : (
          <ul className="divide-y rounded-md border text-xs">
            {runs.map((r) => (
              <li key={r.id} className="flex flex-wrap justify-between gap-2 p-2">
                <span>
                  {fmt.format(new Date(r.started_at))} · {r.source_key} · {r.trigger}
                </span>
                <span>
                  <span
                    className={
                      r.status === "failed"
                        ? "text-red-700"
                        : r.status === "capped"
                          ? "text-amber-700"
                          : ""
                    }
                  >
                    {r.status}
                  </span>
                  {" · "}
                  {r.queries} queries · {r.fetched} fetched · {r.new_items} new · $
                  {r.cost_usd.toFixed(4)}
                </span>
                {r.error && <span className="w-full text-red-700">{r.error}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Latest raw items</h2>
        <ul className="divide-y rounded-md border text-sm">
          {items.map((i) => (
            <li key={i.id} className="flex flex-col gap-1 p-3">
              <span className="text-xs text-neutral-500">
                {i.source_key} · {i.visibility} · {i.author_handle ?? "unknown author"} ·{" "}
                {fmt.format(new Date(i.fetched_at))}
              </span>
              {/* Outside content is always rendered as plain text (React escapes it). */}
              <span className="font-medium">{i.title ?? "(no title)"}</span>
              {i.body && <span className="whitespace-pre-line text-neutral-600">{i.body}</span>}
              {i.url && <span className="break-all text-xs text-neutral-500">{i.url}</span>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
