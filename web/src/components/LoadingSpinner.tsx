export function LoadingSpinner() {
  return (
    <div
      role="status"
      aria-busy="true"
      className="flex min-h-[60vh] items-center justify-center"
    >
      <span className="sr-only">Loading…</span>
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white" />
    </div>
  );
}
