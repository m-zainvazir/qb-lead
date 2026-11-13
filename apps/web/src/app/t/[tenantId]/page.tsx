import Link from "next/link";
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
      <section className="flex flex-col gap-2 rounded-md border border-dashed p-6 text-sm text-neutral-600">
        <p>No leads yet. Your lead inbox arrives once sources and matching are set up.</p>
        <p>
          Meanwhile, check{" "}
          <Link href={`/t/${company.id}/profile`} className="underline">
            what we will look for
          </Link>
          {company.role !== "member" && (
            <>
              {" "}
              or{" "}
              <Link href={`/t/${company.id}/onboarding`} className="underline">
                answer the setup questions
              </Link>
            </>
          )}
          .
        </p>
      </section>
    </>
  );
}
