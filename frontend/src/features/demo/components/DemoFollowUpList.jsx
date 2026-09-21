import EmptyState from "@/shared/components/EmptyState";
import { FollowUpKindBadge, StatusBadge } from "@/shared/components/StatusBadge";
import { Card } from "@/shared/components/ui";

/**
 * The follow-up drafts, read-only.
 *
 * This list is the "it chases only what is missing" story, so `requested_labels`
 * — the fields the agent *decided to ask for*, worded for the supplier — is the
 * payload that carries it, and it is rendered as chips rather than as prose.
 * A draft with no requested fields is a first reminder about a silent supplier, not
 * an incomplete-quote chase, and is labelled as such instead of showing an empty
 * gap that would read like missing data.
 *
 * No approve/edit/reject control is rendered. Those verbs exist for a signed-in
 * buyer; here the message is shown as the record of what the agent decided, with
 * the recipient named as "would go to" so the visitor is never left wondering
 * whether a real contractor just received an email.
 */

function DemoFollowUpList({ followups = [] }) {
  if (!followups.length) {
    return (
      <EmptyState
        title="No follow-up drafts in this sample"
        description="A draft appears here when a supplier has gone quiet or sent a quote that is missing a required field."
      />
    );
  }

  // Drafts awaiting a decision first, then everything already sent. `Array.sort`
  // is stable, so drafts keep the API's order relative to each other.
  const ordered = [...followups].sort(
    (a, b) => (a.status === "draft" ? 0 : 1) - (b.status === "draft" ? 0 : 1)
  );

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border-default bg-surface-2 px-5 py-3">
        <p className="text-xs leading-relaxed text-muted">
          Each draft asks for only what is still missing — never for the whole
          quote again. Nothing here has been sent.
        </p>
      </div>

      <ul className="divide-y divide-border-default">
        {ordered.map((followup) => (
          <li key={followup.id} className="px-5 py-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-content">
                {followup.supplier_name}
              </span>

              <FollowUpKindBadge kind={followup.kind} />

              <span title={followup.status_label || undefined}>
                <StatusBadge status={followup.status} domain="followup" />
              </span>
            </div>

            {(followup.requested_labels || []).length > 0 ? (
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
                  Asked for
                </span>

                {followup.requested_labels.map((label) => (
                  <span
                    key={label}
                    className="rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-medium text-warning-soft-fg"
                  >
                    {label}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-2.5 text-[11px] font-medium text-subtle">
                No specific fields — this one simply asks whether they intend to
                quote at all.
              </p>
            )}

            {followup.subject && (
              <p className="mt-2.5 truncate text-xs text-muted" title={followup.subject}>
                {followup.subject}
              </p>
            )}

            <p className="mt-1 truncate text-[11px] text-subtle">
              Would go to {followup.to_email}
            </p>

            {followup.decision_reason && (
              <p className="mt-2 text-xs leading-relaxed text-subtle">
                {followup.decision_reason}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default DemoFollowUpList;
