/**
 * Loading placeholder shaped like the real form.
 *
 * A skeleton that matches the final layout prevents the "did it freeze?" moment
 * on a slow mobile connection, and it reserves the header height so nothing
 * jumps when the invitation arrives.
 */
export default function LoadingSkeleton() {
  return (
    <div className="min-h-screen" aria-busy="true">
      <header className="border-b border-border-default bg-surface">
        <div className="mx-auto w-full max-w-2xl px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 animate-pulse rounded-xl bg-surface-2" />
            <div className="space-y-2">
              <div className="h-4 w-40 animate-pulse rounded bg-surface-2" />
              <div className="h-3 w-24 animate-pulse rounded bg-surface-2" />
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <div className="h-6 w-3/4 animate-pulse rounded bg-surface-2" />
            <div className="h-4 w-1/2 animate-pulse rounded bg-surface-2" />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl space-y-4 px-4 py-6">
        <div className="h-24 animate-pulse rounded-2xl border border-border-default bg-surface" />
        {[0, 1, 2].map((group) => (
          <div
            key={group}
            className="space-y-4 rounded-2xl border border-border-default bg-surface p-4"
          >
            <div className="h-4 w-32 animate-pulse rounded bg-surface-2" />
            {[0, 1].map((row) => (
              <div key={row} className="space-y-2">
                <div className="h-3 w-24 animate-pulse rounded bg-surface-2" />
                <div className="h-12 animate-pulse rounded-xl bg-surface-2" />
              </div>
            ))}
          </div>
        ))}
      </main>

      {/* Announced once for screen readers; the visual skeleton is decorative. */}
      <p role="status" className="sr-only">
        Loading your quote request…
      </p>
    </div>
  );
}
