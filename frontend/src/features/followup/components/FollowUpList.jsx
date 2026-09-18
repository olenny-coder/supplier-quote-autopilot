import { useState } from "react";

import { toast } from "sonner";

import ConfirmModal from "@/shared/components/ConfirmModal";
import EmptyState from "@/shared/components/EmptyState";
import { SkeletonCard } from "@/shared/components/Loading";
import Modal from "@/shared/components/Modal";
import { Badge, Button, Card, FormField, inputClass } from "@/shared/components/ui";
import { formatDateTime, formatRelativeTime } from "@/shared/lib/format";
import {
  FollowUpKindBadge,
  StatusBadge,
} from "@/shared/components/StatusBadge";

import { approveFollowUp, rejectFollowUp } from "../api";

/**
 * The shared follow-up log.
 *
 * Rendered by this slice's approval queue *and* by the RFQ detail
 * "Follow-ups" tab, so it is purely presentational: the parent owns the data
 * and passes `onChanged` to reload after Approve / Discard. It never fetches.
 */

const errorClass = "border-danger/60 bg-danger-soft/40";

/** Marks copy the AI assistant wrote, so a buyer knows to read it closely. */
function AiDraftedBadge() {
  return (
    <Badge variant="primary">
      <svg
        className="h-3 w-3"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 4l1.7 4.3L18 10l-4.3 1.7L12 16l-1.7-4.3L6 10l4.3-1.7L12 4z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z"
        />
      </svg>
      AI-drafted
    </Badge>
  );
}

function FollowUpRow({ followup, onChanged }) {
  const [showBody, setShowBody] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showDiscardModal, setShowDiscardModal] = useState(false);
  const [subject, setSubject] = useState(followup.subject || "");
  const [body, setBody] = useState(followup.body || "");
  const [errors, setErrors] = useState({});
  const [isApproving, setIsApproving] = useState(false);
  const [isDiscarding, setIsDiscarding] = useState(false);

  const canDecide = followup.status === "draft" || followup.status === "queued";

  const requestedLabels = Array.isArray(followup.requested_labels)
    ? followup.requested_labels.filter(Boolean)
    : [];

  const openApproveModal = () => {
    setSubject(followup.subject || "");
    setBody(followup.body || "");
    setErrors({});
    setShowApproveModal(true);
  };

  const validate = () => {
    const nextErrors = {};

    if (!subject.trim()) {
      nextErrors.subject = "Add a subject line before sending this message.";
    }

    if (!body.trim()) {
      nextErrors.body = "The message body cannot be empty.";
    }

    return nextErrors;
  };

  const handleApprove = async (event) => {
    event.preventDefault();

    const nextErrors = validate();

    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    setErrors({});
    setIsApproving(true);

    try {
      const result = await approveFollowUp(followup.id, { subject, body });

      toast.success(result?.message || "Follow-up approved and queued for sending.");

      setShowApproveModal(false);
      onChanged?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsApproving(false);
    }
  };

  const handleDiscard = async () => {
    setIsDiscarding(true);

    try {
      const result = await rejectFollowUp(followup.id);

      toast.success(result?.message || "Draft discarded — no message will be sent.");

      setShowDiscardModal(false);
      onChanged?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsDiscarding(false);
    }
  };

  return (
    <Card className="p-5 sm:p-6">
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <FollowUpKindBadge kind={followup.kind} />
            <StatusBadge status={followup.status} domain="followup" />
            {followup.llm_generated && <AiDraftedBadge />}
          </div>

          <div className="text-right">
            <p className="text-sm font-medium text-content">
              {followup.supplier_name || "Unknown supplier"}
            </p>
            <p className="text-xs text-subtle">
              {followup.to_email || "No recipient address"}
            </p>
          </div>
        </div>

        {(followup.rfq_number || followup.item_name) && (
          <p className="text-xs text-subtle">
            {[followup.rfq_number, followup.item_name].filter(Boolean).join(" · ")}
          </p>
        )}

        <div className="space-y-2">
          <h3 className="text-base font-semibold text-content">
            {followup.subject || "(No subject yet)"}
          </h3>

          {followup.decision_reason && (
            <p className="text-sm text-muted">{followup.decision_reason}</p>
          )}
        </div>

        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowBody((previous) => !previous)}
          >
            <svg
              className={`h-4 w-4 transition-transform ${showBody ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
            {showBody ? "Hide message" : "Show message"}
          </Button>
        </div>

        {showBody && (
          <div className="space-y-3">
            <div className="whitespace-pre-wrap rounded-xl border border-border-default bg-surface-2 p-4 text-sm leading-relaxed text-content">
              {followup.body || "This draft has no message body yet."}
            </div>

            {requestedLabels.length > 0 && (
              <div>
                <p className="text-xs font-medium tracking-wide text-subtle uppercase">
                  Requested fields
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {requestedLabels.map((label) => (
                    <Badge key={label} variant="neutral">
                      {label}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {followup.error && (
          <div className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger-soft-fg">
            <p className="font-semibold">Delivery failed</p>
            <p className="mt-0.5 break-words">{followup.error}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-subtle">
          <span>
            {followup.sequence ? `Message ${followup.sequence} · ` : ""}
            Created {formatDateTime(followup.created_at)}
          </span>

          {followup.sent_at && (
            <span>
              Sent {formatDateTime(followup.sent_at)} (
              {formatRelativeTime(followup.sent_at)})
            </span>
          )}

          {followup.scheduled_for && (
            <span>
              Scheduled {formatDateTime(followup.scheduled_for)} (
              {formatRelativeTime(followup.scheduled_for)})
            </span>
          )}

          {followup.approved_at && (
            <span>Approved {formatDateTime(followup.approved_at)}</span>
          )}
        </div>

        {canDecide && (
          <div className="flex flex-wrap justify-end gap-3 border-t border-border-default pt-4">
            <Button
              variant="soft-danger"
              size="sm"
              onClick={() => setShowDiscardModal(true)}
            >
              Discard
            </Button>
            <Button size="sm" onClick={openApproveModal}>
              Approve &amp; send
            </Button>
          </div>
        )}
      </div>

      <Modal
        isOpen={showApproveModal}
        onClose={() => setShowApproveModal(false)}
        title="Approve & send"
        description={`This message goes to ${
          followup.to_email || "the supplier"
        } as soon as you approve it.`}
      >
        <form onSubmit={handleApprove} className="space-y-5">
          <FormField label="Subject" required error={errors.subject}>
            <input
              type="text"
              value={subject}
              onChange={(event) => {
                setSubject(event.target.value);
                if (errors.subject) setErrors((previous) => ({ ...previous, subject: null }));
              }}
              placeholder="e.g. Reminder: quote for Steel Bolt M10"
              className={`${inputClass} ${errors.subject ? errorClass : ""}`}
            />
          </FormField>

          <FormField label="Message" required error={errors.body}>
            <textarea
              rows={10}
              value={body}
              onChange={(event) => {
                setBody(event.target.value);
                if (errors.body) setErrors((previous) => ({ ...previous, body: null }));
              }}
              placeholder="Write the message the supplier will receive..."
              className={`${inputClass} resize-y ${errors.body ? errorClass : ""}`}
            />
          </FormField>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowApproveModal(false)}
            >
              Cancel
            </Button>
            <Button type="submit" loading={isApproving} loadingText="Sending…">
              Approve &amp; send
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmModal
        isOpen={showDiscardModal}
        onClose={() => setShowDiscardModal(false)}
        onConfirm={handleDiscard}
        title="Discard this draft"
        description={`The message to ${
          followup.supplier_name || followup.to_email || "this supplier"
        } will be marked as discarded and nothing will be emailed.`}
        confirmText="Discard draft"
        isLoading={isDiscarding}
      />
    </Card>
  );
}

function FollowUpList({
  followups = [],
  loading = false,
  onChanged,
  emptyTitle = "Nothing to review",
  emptyDescription = "Follow-up messages appear here as soon as the assistant drafts them.",
}) {
  if (loading) {
    return (
      <div className="grid gap-4 sm:gap-5">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (followups.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <div className="grid gap-4 sm:gap-5">
      {followups.map((followup) => (
        <FollowUpRow key={followup.id} followup={followup} onChanged={onChanged} />
      ))}
    </div>
  );
}

export default FollowUpList;
