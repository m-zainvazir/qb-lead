import { NextResponse, type NextRequest } from "next/server";

import { UUID_RE } from "@/lib/api";

// Company switch: remember the choice, then open the company. The cookie is only a
// convenience; every API call re-checks membership for the company in the URL.
export async function GET(request: NextRequest, ctx: RouteContext<"/switch/[tenantId]">) {
  const { tenantId } = await ctx.params;
  if (!UUID_RE.test(tenantId)) {
    return NextResponse.redirect(new URL("/app?pick=1", request.nextUrl.origin));
  }
  const res = NextResponse.redirect(new URL(`/t/${tenantId}`, request.nextUrl.origin));
  res.cookies.set("last_tenant", tenantId, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 90,
  });
  return res;
}
