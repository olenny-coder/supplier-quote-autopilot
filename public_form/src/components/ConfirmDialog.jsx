import { useEffect, useRef } from "react";

/**
 * Small confirmation dialog.
 *
 * Used for the "you left required details blank — submit anyway?" warning,
 * which must be an explicit choice rather than an alert(): an alert is ugly,
 * untranslatable by browsers' UI, and easy to dismiss without reading.
 *
 * Accessibility handled here: focus moves to the confirm button on open, Escape
 * cancels, the backdrop closes on click, the page behind cannot scroll, and the
 * dialog is a real `role="dialog"` with `aria-modal` so screen readers stay
 * inside it.
 */
export default function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel = "Submit anyway",
  cancelLabel = "Go back and fill it in",
  busy = false,
  onConfirm,
  onCancel,
}) {
  const confirmRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    confirmRef.current?.focus();

    function onKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel?.();
      }
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      // Fixed overlay; the rgba value is inline rather than a Tailwind theme
      // colour so the scrim is never affected by a token change.
      className="fixed inset-0 z-50 flex items-end justify-center bg-[rgba(15,23,42,0.55)] p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel?.();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="w-full max-w-md rounded-t-2xl bg-surface p-5 shadow-pop sm:rounded-2xl"
        style={{ paddingBottom: "calc(1.25rem + var(--safe-bottom))" }}
      >
        <h2
          id="confirm-dialog-title"
          className="text-lg font-bold leading-6 text-content"
        >
          {title}
        </h2>
        <div className="mt-2 space-y-2 text-sm leading-6 text-muted">
          {children}
        </div>

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={() => onCancel?.()}
            className="min-h-[48px] rounded-xl border border-border-strong bg-surface px-4 text-base font-semibold text-content transition-colors hover:bg-surface-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={() => onConfirm?.()}
            disabled={busy}
            className="min-h-[48px] rounded-xl bg-primary px-4 text-base font-semibold text-primary-fg transition-colors hover:bg-primary-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-70"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
