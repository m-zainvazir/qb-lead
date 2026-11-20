import "server-only";

import { createServerClient } from "@supabase/ssr";
import { io } from "next/cache";
import { cookies } from "next/headers";

import { env } from "@/lib/env";
import { hardenCookie } from "@/lib/supabase/cookies";

// A new client per request (never shared). Used by server components, server actions
// and route handlers. The browser never gets a Supabase client or a token.
export async function createClient() {
  const cookieStore = await cookies();
  // The auth client reads the clock as soon as it is created (session expiry). Prefetch
  // prerenders can resolve cookies, so stop every prerender here: auth only runs per request.
  await io();
  return createServerClient(env.supabaseUrl, env.supabaseAnonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(toSet) {
        try {
          for (const { name, value, options } of toSet) {
            cookieStore.set(name, value, hardenCookie(options));
          }
        } catch {
          // Server components cannot set cookies; src/proxy.ts refreshes the session instead.
        }
      },
    },
  });
}
