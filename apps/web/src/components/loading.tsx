export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p role="status" aria-live="polite" className="text-sm text-neutral-500">
      {label}
    </p>
  );
}
