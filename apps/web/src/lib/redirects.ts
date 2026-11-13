// Only same-site relative paths are allowed as post-login destinations (no open redirects).
export function safeNext(next: string | null | undefined, fallback = "/app"): string {
  if (!next) return fallback;
  let candidate = next;
  try {
    // Email templates pass a full URL; keep only its path if it is on our own site.
    if (/^https?:\/\//i.test(candidate)) {
      const url = new URL(candidate);
      const base = new URL(process.env.WEB_BASE_URL ?? "http://localhost:3000");
      if (url.origin !== base.origin) return fallback;
      candidate = url.pathname + url.search;
    }
  } catch {
    return fallback;
  }
  if (!candidate.startsWith("/") || candidate.startsWith("//") || candidate.includes("\\")) {
    return fallback;
  }
  return candidate;
}
