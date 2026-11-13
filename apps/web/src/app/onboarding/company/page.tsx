import Link from "next/link";

import { ActionForm, Field } from "@/components/action-form";
import { createCompany } from "./actions";

export default function CreateCompanyPage() {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 px-4 py-16">
      <h1 className="text-2xl font-semibold">Create your company</h1>
      <p className="text-sm text-neutral-600">
        You will be its owner. You can invite teammates afterwards.
      </p>
      <ActionForm action={createCompany} submitLabel="Create company">
        <Field name="name" label="Company name" maxLength={120} autoComplete="organization" />
        <fieldset className="flex flex-col gap-2 text-sm">
          <legend className="font-medium">You are</legend>
          <label className="flex items-center gap-2">
            <input type="radio" name="type" value="agency" defaultChecked /> An agency
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name="type" value="freelancer" /> A freelancer
          </label>
        </fieldset>
      </ActionForm>
      <Link href="/app?pick=1" className="text-sm underline">
        Back
      </Link>
    </main>
  );
}
