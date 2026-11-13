import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { loadCompany } from "./company";

export default function CompanyHome({ params }: PageProps<"/t/[tenantId]">) {
  return (
    <Suspense fallback={<Loading />}>
      <Home params={params} />
    </Suspense>
  );
}

async function Home({ params }: Pick<PageProps<"/t/[tenantId]">, "params">) {
  const { tenantId } = await params;
  const { me, company } = await loadCompany(tenantId);
  return (
    <>
      <h1 className="text-2xl font-semibold">{company.name}</h1>
      <p className="text-sm text-neutral-600">
        Signed in as {me.email}, {company.role} of this {company.type}.
      </p>
      <section className="rounded-md border border-dashed p-6 text-sm text-neutral-600">
        No leads yet. Your lead inbox arrives once sources and matching are set up.
      </section>
    </>
  );
}
