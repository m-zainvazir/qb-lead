import "server-only";

// Server-side configuration. Nothing here is NEXT_PUBLIC_, so none of it reaches the
// browser bundle. A missing value fails loudly instead of half-working.
function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable ${name}`);
  return value;
}

export const env = {
  get supabaseUrl() {
    return required("SUPABASE_URL");
  },
  get supabaseAnonKey() {
    return required("SUPABASE_ANON_KEY");
  },
  get apiUrl() {
    return required("API_URL");
  },
  // The API address customers' websites post to (defaults to API_URL locally).
  get publicApiUrl() {
    return process.env.PUBLIC_API_URL || required("API_URL");
  },
  get webBaseUrl() {
    return required("WEB_BASE_URL");
  },
  get isProduction() {
    return process.env.NODE_ENV === "production";
  },
};
