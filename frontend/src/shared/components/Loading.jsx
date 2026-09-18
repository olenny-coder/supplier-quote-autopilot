function Loading({ message = "Loading..." }) {
  return (
    <div className="flex w-full flex-col items-center justify-center gap-4 py-24">
      <div className="relative h-10 w-10">
        <div className="absolute inset-0 rounded-full border-2 border-border-default" />
        <div className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-primary" />
      </div>
      <p className="text-sm font-medium text-muted">{message}</p>
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-2xl border border-border-default bg-surface p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-3">
          <div className="h-5 w-1/3 rounded-lg bg-surface-2" />
          <div className="h-3.5 w-2/3 rounded bg-surface-2" />
          <div className="h-3.5 w-1/4 rounded bg-surface-2" />
        </div>
        <div className="h-9 w-24 rounded-lg bg-surface-2" />
      </div>
    </div>
  );
}

export default Loading;
