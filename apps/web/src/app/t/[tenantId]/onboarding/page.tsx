import { notFound, unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { Loading } from "@/components/loading";
import { api, ApiError } from "@/lib/api";
import { loadCompany } from "../company";
import type { Answers } from "./actions";
import { Wizard, type CatalogueOption, type Question } from "./wizard";

type Onboarding = {
  questions: Question[];
  options: Record<string, CatalogueOption[]>;
  progress: { current_step: number; answers: Answers; completed_at: string | null } | null;
  steps: number;
};

export default function OnboardingPage({ params }: PageProps<"/t/[tenantId]/onboarding">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Tell us about your business</h1>
      <p className="max-w-xl text-sm text-neutral-600">
        A few short questions. They decide which leads we look for and how proposals sound.
      </p>
      <Suspense fallback={<Loading label="Loading the questions…" />}>
        <Questions params={params} />
      </Suspense>
    </>
  );
}

async function Questions({ params }: Pick<PageProps<"/t/[tenantId]/onboarding">, "params">) {
  const { tenantId } = await params;
  const { company } = await loadCompany(tenantId);
  if (company.role === "member") {
    return (
      <p role="alert" className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
        Only owners and admins of {company.name} can change the profile.
      </p>
    );
  }
  let data: Onboarding;
  try {
    data = await api<Onboarding>("/onboarding", { tenantId });
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && err.status === 403) notFound();
    return (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
        Could not load the questions. Reload to try again.
      </p>
    );
  }
  return (
    <Wizard
      tenantId={tenantId}
      questions={data.questions}
      options={data.options}
      steps={data.steps}
      initialStep={data.progress?.current_step ?? 1}
      initialAnswers={data.progress?.answers ?? {}}
    />
  );
}
