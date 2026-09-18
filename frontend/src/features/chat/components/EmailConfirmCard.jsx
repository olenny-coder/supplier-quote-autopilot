import { Button } from "@/shared/components/ui";

/*
 * Renders a drafted supplier email with explicit Send / Cancel controls. The
 * email is only sent when the buyer presses Send — the orchestrator never sends
 * on its own. `status` drives the card between its review / sent / cancelled
 * states.
 */

function Field({ label, children }) {
  return (
    <div className="flex gap-2 text-xs">
      <span className="w-14 shrink-0 font-medium text-subtle">{label}</span>
      <span className="min-w-0 flex-1 break-words text-content">{children}</span>
    </div>
  );
}

function EmailConfirmCard({ draft, status = "pending", error, onConfirm, onCancel }) {
  const sending = status === "sending";
  const sent = status === "sent";
  const cancelled = status === "cancelled";
  const resolved = sent || cancelled;

  return (
    <div className="mt-2 overflow-hidden rounded-2xl border border-border-default bg-surface-2/60">
      <div className="flex items-center gap-2 border-b border-border-default px-3.5 py-2">
        <svg
          className="h-4 w-4 text-primary"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 8l9 6 9-6M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
        <span className="text-xs font-semibold text-content">Draft email</span>
        {sent && (
          <span className="ml-auto rounded-full bg-success-soft px-2 py-0.5 text-[0.7rem] font-medium text-success-soft-fg">
            Sent
          </span>
        )}
        {cancelled && (
          <span className="ml-auto rounded-full bg-surface px-2 py-0.5 text-[0.7rem] font-medium text-subtle">
            Cancelled
          </span>
        )}
      </div>

      <div className="space-y-1.5 px-3.5 py-3">
        <Field label="To">
          {draft.to_name ? (
            <>
              {draft.to_name}{" "}
              <span className="text-muted">&lt;{draft.to_email}&gt;</span>
            </>
          ) : (
            draft.to_email
          )}
        </Field>
        <Field label="Subject">{draft.subject}</Field>
        <div className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-xl bg-surface-inset px-3 py-2 text-xs leading-relaxed text-content">
          {draft.body}
        </div>
      </div>

      {error && (
        <p className="px-3.5 pb-2 text-xs text-danger">{error}</p>
      )}

      {!resolved && (
        <div className="flex items-center justify-end gap-2 border-t border-border-default px-3 py-2.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={onCancel}
            disabled={sending}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={onConfirm}
            loading={sending}
            loadingText="Sending…"
          >
            Send email
          </Button>
        </div>
      )}
    </div>
  );
}

export default EmailConfirmCard;
