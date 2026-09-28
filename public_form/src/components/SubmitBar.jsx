/**
 * Sticky submit action bar.
 *
 * On a phone the supplier's thumb lives at the bottom of the screen, so the
 * primary action stays reachable without scrolling back through seventeen
 * fields. It becomes a normal in-flow block from `sm` up, where the whole form
 * is visible at once.
 *
 * It carries its own background — `bg-bg` while it is pinned over the page,
 * `bg-surface` once it is a card in the flow — because it floats above the form
 * and cannot inherit one. Both are semantic tokens, so the bar restyles with the
 * theme like everything else; there is deliberately no fixed colour here.
 *
 * Lifted out of `QuoteFormPage` only so it can be rendered and checked on its
 * own (it is a self-contained piece of chrome). It holds no state and does not
 * touch submission: the page still owns `onSubmit`, the button is still
 * `type="submit"`, and this component only draws what it is handed.
 */
export default function SubmitBar({
  status = "idle",
  message = "",
  submitting = false,
  label,
  hasRequiredFields = false,
}) {
  return (
    <div
      className="sticky bottom-0 z-20 -mx-4 mt-2 border-t border-border-default bg-bg px-4 pt-3 sm:static sm:mx-0 sm:rounded-2xl sm:border sm:border-border-default sm:bg-surface sm:p-4"
      style={{ paddingBottom: "calc(0.75rem + var(--safe-bottom))" }}
    >
      <p
        aria-live="polite"
        className={[
          "mb-2 text-sm font-medium",
          status === "error"
            ? "text-danger-soft-fg"
            : status === "success"
              ? "text-success-soft-fg"
              : "text-muted",
        ].join(" ")}
      >
        {message}
      </p>

      <button
        type="submit"
        disabled={submitting}
        className="min-h-[52px] w-full rounded-xl bg-primary px-5 text-base font-semibold text-primary-fg transition-colors hover:bg-primary-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-70"
      >
        {submitting ? "Sending…" : label}
      </button>
      <p className="mt-2 text-center text-xs text-muted">
        {hasRequiredFields
          ? "Fields marked * are what the buyer needs. You can still send a partial quote — they will follow up by email."
          : "You can send this quote as it is."}
      </p>
    </div>
  );
}
