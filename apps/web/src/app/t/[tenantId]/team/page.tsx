import { notFound, unstable_rethrow } from "next/navigation";
import { Suspense } from "react";

import { ActionForm, Field } from "@/components/action-form";
import { Loading } from "@/components/loading";
import { api, ApiError, type Team } from "@/lib/api";
import { loadCompany } from "../company";
import { changeRole, inviteMember, removeMember, revokeInvitation } from "./actions";

const dateFmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export default function TeamPage({ params, searchParams }: PageProps<"/t/[tenantId]/team">) {
  return (
    <>
      <h1 className="text-2xl font-semibold">Team settings</h1>
      <Suspense fallback={<Loading label="Loading your teamâ€¦" />}>
        <TeamSettings params={params} searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function TeamSettings({
  params,
  searchParams,
}: Pick<PageProps<"/t/[tenantId]/team">, "params" | "searchParams">) {
  const { tenantId } = await params;
  const { error } = await searchParams;
  const { me, company } = await loadCompany(tenantId);

  let team: Team;
  try {
    team = await api<Team>("/team", { tenantId });
  } catch (err) {
    unstable_rethrow(err);
    if (err instanceof ApiError && err.status === 403) {
      return (
        <p role="alert" className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
          Access refused. Only owners and admins of {company.name} can open team settings.
        </p>
      );
    }
    if (err instanceof ApiError && err.status === 404) notFound();
    return (
      <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
        Could not load the team. {err instanceof ApiError ? err.message : ""} Reload to try again.
      </p>
    );
  }

  const isOwner = company.role === "owner";
  return (
    <>
      {typeof error === "string" && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="font-semibold">Members ({team.members.length})</h2>
        <ul className="divide-y rounded-md border">
          {team.members.map((m) => {
            const self = m.user_id === me.id;
            return (
              <li
                key={m.user_id}
                className="flex flex-wrap items-center justify-between gap-3 p-3 text-sm"
              >
                <span>
                  {m.email} {self && <span className="text-neutral-500">(you)</span>}
                </span>
                <span className="flex items-center gap-3">
                  {isOwner && !self ? (
                    <form action={changeRole} className="flex items-center gap-2">
                      <input type="hidden" name="tenantId" value={tenantId} />
                      <input type="hidden" name="userId" value={m.user_id} />
                      <select
                        name="role"
                        defaultValue={m.role}
                        className="rounded border px-2 py-1"
                        aria-label={`Role for ${m.email}`}
                      >
                        <option value="owner">owner</option>
                        <option value="admin">admin</option>
                        <option value="member">member</option>
                      </select>
                      <button className="underline">Save</button>
                    </form>
                  ) : (
                    <span className="text-neutral-600">{m.role}</span>
                  )}
                  {isOwner && !self && (
                    <form action={removeMember}>
                      <input type="hidden" name="tenantId" value={tenantId} />
                      <input type="hidden" name="userId" value={m.user_id} />
                      <button className="text-red-700 underline">Remove</button>
                    </form>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-semibold">Pending invitations</h2>
        {team.invitations.length === 0 ? (
          <p className="text-sm text-neutral-500">No pending invitations.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {team.invitations.map((i) => (
              <li
                key={i.id}
                className="flex flex-wrap items-center justify-between gap-3 p-3 text-sm"
              >
                <span>
                  {i.email} as {i.role}
                  <span className="text-neutral-500">
                    {" "}
                    Â· expires {dateFmt.format(new Date(i.expires_at))}
                  </span>
                </span>
                <form action={revokeInvitation}>
                  <input type="hidden" name="tenantId" value={tenantId} />
                  <input type="hidden" name="invitationId" value={i.id} />
                  <button className="underline">Revoke</button>
                </form>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex max-w-sm flex-col gap-3">
        <h2 className="font-semibold">Invite a teammate</h2>
        <ActionForm action={inviteMember.bind(null, tenantId)} submitLabel="Send invitation">
          <Field name="email" label="Email" type="email" maxLength={320} />
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Role</span>
            <select
              name="role"
              defaultValue="member"
              className="rounded-md border border-neutral-300 px-3 py-2"
            >
              <option value="member">member</option>
              {isOwner && <option value="admin">admin</option>}
            </select>
          </label>
        </ActionForm>
      </section>
    </>
  );
}
