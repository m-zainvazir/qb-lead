import type { CookieOptions } from "@supabase/ssr";

// Every auth cookie is HTTP-only: browser JavaScript can never read the session.
export function hardenCookie(options: CookieOptions | undefined): CookieOptions {
  return {
    ...options,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
  };
}
