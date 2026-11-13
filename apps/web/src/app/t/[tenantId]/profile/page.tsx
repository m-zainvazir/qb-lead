import Link from "next/link";
import { unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { api, ApiError } from "@/lib/api";
import { loadCompany } from "../company";
import { AutoRefresh } from "./auto-refresh";

type PreviewItem = {
  title: string;
  source: string;
  market: string | null;
  score: number;
  decision: "reach" | "skip";
  reason: string;
};

type Profile = {
  type: string;
  team_size: number | null;
  min_budget_usd: number;
  client_sizes: string[];
  tone: string;
  priorities: string[];
  time_zone: string;
  version: number;
  compile_status: "pending" | "compiling" | "ready" | "failed";
  compiled_version: number | null;
  services: { id: string; name: string; custom: boolean }[];
  markets: { code: string; name: string }[];
  signals: { key: string; label: string; temperature: string }[];
  exclusions: string[];
  compiled: {
    profile_version: number;
    status: string;
    search_terms: {
      services?: { name: string; phrases: string[]; technologies: string[] }[];
      preview?: PreviewItem[];
    };
  } | null;
};

const STATUS: Record<Profile["compile_status"], string> = {
  pending: "Updating…",
  compiling: "Updating…",
  ready: "Up to date",
  failed: "The last update failed; we retry automatically",
};

export default function ProfilePage({ params }: PageProps<"/t/[tenantId]/profile">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Here is what we will look for</h1>
      <Suspense fallback={<Loading label="Loading your profile…" />}>
        <ProfileView params={params} />
      </Suspense>
    </>
  );
}

async function ProfileView({ params }: Pick<PageProps<"/t/[tenantId]/profile">, "params">) {
  const { tenantId } = await params;
  const { company } = await loadCompany(tenantId);
  let p: Profile;
  try {
    p = await api<Profile>("/profile", { tenantId });
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && err.status === 404) {
      return (
        <div className="flex flex-col gap-3 rounded-md border border-dashed p-6 text-sm">
          <p>You have not set up your profile yet.</p>
          {company.role !== "member" && (
            <Link
              href={`/t/${tenantId}/onboarding`}
              className="self-start rounded-md bg-neutral-900 px-4 py-2 text-white"
            >
              Answer the questions
            </Link>
          )}
        </div>
      );
    }
    return (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
        Could not load the profile. Reload to try again.
      </p>
    );
  }

  const updating = p.compile_status === "pending" || p.compile_status === "compiling";
  const terms = p.compiled?.search_terms ?? {};
  const reach = (terms.preview ?? []).filter((x) => x.decision === "reach").slice(0, 4);
  const skip = (terms.preview ?? []).filter((x) => x.decision === "skip").slice(0, 4);
  const stale = p.compiled && p.compiled.profile_version !== p.version;

  return (
    <div className="flex flex-col gap-8">
      {updating && <AutoRefresh seconds={3} />}
      <p className="flex items-center gap-3 text-sm">
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${updating ? "bg-amber-100 text-amber-900" : p.compile_status === "failed" ? "bg-red-100 text-red-900" : "bg-green-100 text-green-900"}`}
        >
          {STATUS[p.compile_status]}
        </span>
        <span className="text-neutral-500">Profile version {p.version}</span>
        {company.role !== "member" && (
          <Link href={`/t/${tenantId}/onboarding`} className="underline">
            Change answers
          </Link>
        )}
      </p>

      <section className="grid gap-4 sm:grid-cols-2">
        <Card title="Services">
          {p.services.map((s) => (
            <li key={s.id}>
              {s.name}{" "}
              {s.custom && <span className="text-xs text-neutral-500">(only visible to you)</span>}
            </li>
          ))}
        </Card>
        <Card title="Where">
          {p.markets.map((m) => (
            <li key={m.code}>{m.name}</li>
          ))}
        </Card>
        <Card title="Kinds of posts">
          {p.signals.map((s) => (
            <li key={s.key}>
              {s.label} <span className="text-xs text-neutral-500">({s.temperature})</span>
            </li>
          ))}
        </Card>
        <Card title="We will skip posts that mention">
          {p.exclusions.length ? (
            p.exclusions.map((e) => <li key={e}>{e}</li>)
          ) : (
            <li className="text-neutral-500">Nothing excluded</li>
          )}
        </Card>
      </section>

      <p className="text-sm text-neutral-600">
        Projects from ${p.min_budget_usd.toLocaleString()} up · proposals sound {p.tone} · times
        shown in {p.time_zone}
      </p>

      {stale && (
        <p className="text-sm text-amber-800">
          The examples below are from your previous answers; they update in a moment.
        </p>
      )}

      {terms.services && (
        <section className="flex flex-col gap-2">
          <h2 className="font-semibold">Phrases we search for</h2>
          {terms.services.map((s) => (
            <p key={s.name} className="text-sm">
              <span className="font-medium">{s.name}:</span>{" "}
              <span className="text-neutral-600">
                {s.phrases
                  .slice(0, 8)
                  .map((x) => `“${x}”`)
                  .join(", ")}
              </span>
            </p>
          ))}
        </section>
      )}

      {(reach.length > 0 || skip.length > 0) && (
        <section className="grid gap-4 sm:grid-cols-2">
          <Examples
            title="Posts like these would reach you"
            items={reach}
            empty="None of our examples match yet."
          />
          <Examples title="Posts like these we would skip" items={skip} empty="" />
        </section>
      )}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border p-4">
      <h2 className="mb-2 text-sm font-semibold">{title}</h2>
      <ul className="flex flex-col gap-1 text-sm">{children}</ul>
    </div>
  );
}

function Examples({ title, items, empty }: { title: string; items: PreviewItem[]; empty: string }) {
  return (
    <div className="rounded-md border p-4">
      <h2 className="mb-2 text-sm font-semibold">{title}</h2>
      {items.length === 0 ? (
        <p className="text-sm text-neutral-500">{empty}</p>
      ) : (
        <ul className="flex flex-col gap-3 text-sm">
          {items.map((x) => (
            <li key={x.title}>
              <p className="font-medium">“{x.title}”</p>
              <p className="text-neutral-600">This post {x.reason}.</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
