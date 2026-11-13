// Only same-origin paths are allowed as post-login destinations (no open redirects).
// The candidate is resolved the way a browser would resolve it (URL parsers drop tabs
// and newlines, so "/\t/evil.com" means "//evil.com"); only a same-origin result is kept.
export function safeNext(next: string | null | undefined, fallback = "/app"): string {
  if (!next) return fallback;
  // eslint-disable-next-line no-control-regex -- control characters are exactly what we reject
  if (/[\u0000-\u001f\u007f\\]/.test(next)) return fallback;
  try {
    const base = new URL(process.env.WEB_BASE_URL ?? "http://localhost:3000");
    const url = new URL(next, base);
    if (url.origin !== base.origin) return fallback;
    const path = url.pathname + url.search;
    return path.startsWith("//") ? fallback : path;
  } catch {
    return fallback;
  }
}
