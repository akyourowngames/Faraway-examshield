type ErrorFallbackProps = {
  title?: string;
  message: string;
  onRetry?: () => void;
};

export function ErrorFallback({
  title = "Something went wrong",
  message,
  onRetry,
}: ErrorFallbackProps) {
  return (
    <div
      role="alert"
      className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center text-white"
    >
      <h2 className="text-2xl font-heading uppercase tracking-[0.2em]">{title}</h2>
      <p className="max-w-md text-sm text-white/60">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-full bg-white px-6 py-2.5 text-xs font-semibold uppercase tracking-[0.1em] text-black transition-colors hover:bg-white/90"
        >
          Try again
        </button>
      )}
    </div>
  );
}
