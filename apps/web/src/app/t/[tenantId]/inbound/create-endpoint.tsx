"use client";

import { useState, useTransition } from "react";

import { createEndpoint, type CreatedEndpoint } from "./actions";

// The webhook address contains a secret that is shown once and never again.
export function CreateEndpoint({ tenantId }: { tenantId: string }) {
  const [result, setResult] = useState<CreatedEndpoint>(null);
  const [pending, startTransition] = useTransition();
  const create = (kind: "webhook" | "email") =>
    startTransition(async () => setResult(await createEndpoint(tenantId, kind)));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-3">
        <button
          type="button"
          disabled={pending}
          onClick={() => create("webhook")}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          New webhook address
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => create("email")}
          className="rounded-md border px-4 py-2 text-sm disabled:opacity-50"
        >
          New email address
        </button>
      </div>
      {result?.error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {result.error}
        </p>
      )}
      {result?.url && (
        <div
          role="status"
          className="flex flex-col gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-900"
        >
          <p className="font-medium">Copy this address now. It is shown only once.</p>
          <code className="break-all rounded bg-white p-2 text-xs">{result.url}</code>
          <p>Post JSON to it from your website form or n8n, for example:</p>
          <code className="break-all rounded bg-white p-2 text-xs">
            {`curl -X POST "${result.url}" -H "Content-Type: application/json" -d '{"title":"New enquiry","body":"...","url":"https://..."}'`}
          </code>
        </div>
      )}
      {result?.email && (
        <p role="status" className="rounded-md bg-green-50 p-3 text-sm text-green-900">
          Forward job alerts (for example from Upwork) to <code>{result.email}</code>.
        </p>
      )}
    </div>
  );
}
