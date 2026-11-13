import { unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { ActionForm, Field } from "@/components/action-form";
import { Loading } from "@/components/loading";
import { api } from "@/lib/api";
import { AdminRefused } from "../shared";
import { addService, setActive } from "./actions";

type Row = { id: string; is_active: boolean; [key: string]: unknown };
type Catalogue = {
  services: Row[];
  markets: Row[];
  signal_types: Row[];
  onboarding_questions: Row[];
};

export default function CataloguePage() {
  return (
    <>
      <h1 className="text-2xl font-semibold">Catalogue</h1>
      <p className="text-sm text-neutral-600">
        Shared by every company. Changes are data: they show up in onboarding at once, no deploy.
      </p>
      <Suspense fallback={<Loading />}>
        <CatalogueView />
      </Suspense>
    </>
  );
}

async function CatalogueView() {
  let c: Catalogue;
  try {
    c = await api<Catalogue>("/admin/catalogue");
  } catch (err) {
    unstable_rethrow(err);
    return <AdminRefused error={err} />;
  }
  return (
    <div className="flex flex-col gap-8">
      <section className="max-w-md">
        <h2 className="mb-2 font-semibold">Add a service</h2>
        <ActionForm action={addService} submitLabel="Add service">
          <Field name="name" label="Name" maxLength={120} />
          <Field
            name="slug"
            label="Slug (optional, e.g. chatbots)"
            required={false}
            maxLength={60}
          />
          <Field name="description" label="Description" required={false} maxLength={2000} />
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Problems, one per line: label | phrase; phrase</span>
            <textarea
              name="problems"
              rows={4}
              className="rounded-md border border-neutral-300 px-3 py-2"
            />
          </label>
        </ActionForm>
      </section>
      <List
        title="Services"
        kind="services"
        rows={c.services}
        label={(r) => `${r.name} (${r.problems} problems)`}
      />
      <List
        title="Markets"
        kind="markets"
        rows={c.markets}
        label={(r) => `${r.name} · weight ${r.default_weight}`}
      />
      <List
        title="Signal types"
        kind="signal_types"
        rows={c.signal_types}
        label={(r) => `${r.label} (${r.temperature})`}
      />
      <List
        title="Questions"
        kind="onboarding_questions"
        rows={c.onboarding_questions}
        label={(r) => `Step ${r.step}: ${r.label}`}
      />
    </div>
  );
}

function List({
  title,
  kind,
  rows,
  label,
}: {
  title: string;
  kind: string;
  rows: Row[];
  label: (r: Row) => string;
}) {
  return (
    <section>
      <h2 className="mb-2 font-semibold">{title}</h2>
      <ul className="divide-y rounded-md border text-sm">
        {rows.map((r) => (
          <li key={r.id} className="flex items-center justify-between p-2">
            <span className={r.is_active ? "" : "text-neutral-400 line-through"}>{label(r)}</span>
            <form action={setActive}>
              <input type="hidden" name="kind" value={kind} />
              <input type="hidden" name="id" value={r.id} />
              <input type="hidden" name="active" value={r.is_active ? "false" : "true"} />
              <button className="text-xs underline">
                {r.is_active ? "Switch off" : "Switch on"}
              </button>
            </form>
          </li>
        ))}
      </ul>
    </section>
  );
}
