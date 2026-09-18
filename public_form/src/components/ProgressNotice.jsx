/**
 * Small step indicator with a required-details completion bar.
 *
 * Suppliers abandon forms they cannot tell the end of, so this answers two
 * questions at a glance on a phone: "how much is left?" and "what happens
 * after I send?". It is intentionally *not* a blocking wizard — the API accepts
 * partial quotes, so the bar reports progress and never gates it.
 */
export default function ProgressNotice({
  currentStep = 0,
  requiredKeys = [],
  values = {},
  itemName,
}) {
  const steps = ["Quote details", "Confirmation"];
  const total = requiredKeys.length;
  const filled = requiredKeys.filter(
    (key) => String(values[key] ?? "").trim() !== ""
  ).length;
  const percent = total === 0 ? 100 : Math.round((filled / total) * 100);

  return (
    <section
      aria-label="Form progress"
      className="rounded-2xl border border-border-default bg-surface p-4 shadow-card"
    >
      <ol className="flex items-center gap-2 text-xs font-semibold">
        {steps.map((step, index) => {
          const state =
            index < currentStep
              ? "done"
              : index === currentStep
                ? "current"
                : "todo";
          return (
            <li key={step} className="flex flex-1 items-center gap-2">
              <span
                className={[
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold",
                  state === "done"
                    ? "border-success bg-success-soft text-success-soft-fg"
                    : state === "current"
                      ? "border-primary bg-primary text-primary-fg"
                      : "border-border-strong bg-surface-2 text-subtle",
                ].join(" ")}
                aria-hidden="true"
              >
                {state === "done" ? "\u2713" : index + 1}
              </span>
              <span
                className={
                  state === "todo" ? "text-subtle" : "text-content"
                }
              >
                {step}
              </span>
              {index < steps.length - 1 ? (
                <span
                  aria-hidden="true"
                  className="ml-1 hidden h-px flex-1 bg-border-default sm:block"
                />
              ) : null}
            </li>
          );
        })}
      </ol>

      <div className="mt-4 space-y-1.5">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-sm font-medium text-content">
            {total === 0
              ? "No fields are marked as required by the buyer."
              : filled === total
                ? "All the buyer's required details are filled in."
                : `${filled} of ${total} required details filled in`}
          </p>
          <p className="shrink-0 text-xs font-semibold text-muted">
            {percent}%
          </p>
        </div>
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-surface-2"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          aria-label="Required details completed"
        >
          <div
            className={[
              "h-full rounded-full transition-[width] duration-300",
              percent === 100 ? "bg-success" : "bg-primary",
            ].join(" ")}
            style={{ width: `${percent}%` }}
          />
        </div>
        {itemName ? (
          <p className="text-xs text-muted">
            You are quoting for <strong className="font-semibold">{itemName}</strong>.
            Anything you leave blank is recorded, and the buyer will follow up by
            email.
          </p>
        ) : null}
      </div>
    </section>
  );
}
