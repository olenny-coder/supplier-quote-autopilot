import { useMemo, useState } from "react";

import { toast } from "sonner";

import ConfirmModal from "@/shared/components/ConfirmModal";
import EmptyState from "@/shared/components/EmptyState";
import { Button, Card } from "@/shared/components/ui";
import { copyToClipboard } from "@/shared/lib/clipboard";
import {
  formatDateTime,
  formatFieldKey,
  formatNumber,
  formatRelativeTime,
} from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

import { createManualFollowUp } from "@/features/followup/api";

import { cancelInvitation, resendInvitation } from "../api";
import InviteSuppliersPanel from "./InviteSuppliersPanel";

/**
 * Tab 1 — Suppliers & links.
 *
 * One row per invitation: whether it was sent, whether it was opened, how many
 * reminders have gone out, and exactly which fields are missing from an
 * incomplete quote. The row actions are the whole chase workflow: copy the
 * private link, email it again, send a reminder, chase the missing fields, or
 * withdraw the invitation.
 */
function InvitationsTab({ rfqId, invitations = [], onChanged, focusInvitationId }) {
  // Tracks "which row, which action" so only the clicked button shows a spinner.
  const [pending, setPending] = useState(null);
  const [cancelTarget, setCancelTarget] = useState(null);

  const counts = useMemo(() => {
    const total = invitations.length;

    const responded = invitations.filter(
      (invitation) => invitation.status === "submitted"
    ).length;

    const incomplete = invitations.filter(
      (invitation) => invitation.status === "incomplete"
    ).length;

    const pendingCount = invitations.filter((invitation) =>
      ["pending", "expired"].includes(invitation.status)
    ).length;

    return { total, responded, incomplete, pendingCount };
  }, [invitations]);

  const runAction = async (key, action) => {
    try {
      setPending(key);
      await action();
    } finally {
      setPending(null);
    }
  };

  const handleCopyLink = (invitation) =>
    runAction(`copy-${invitation.id}`, async () => {
      if (!invitation.form_link) {
        toast.error("This invitation has no form link yet.");
        return;
      }

      const copied = await copyToClipboard(invitation.form_link);

      if (copied) {
        toast.success(`Form link for ${invitation.supplier_name} copied.`);
      } else {
        toast.error("Could not access the clipboard — open the form and copy the URL.");
      }
    });

  const handleOpenForm = (invitation) => {
    if (!invitation.form_link) {
      toast.error("This invitation has no form link yet.");
      return;
    }

    window.open(invitation.form_link, "_blank", "noopener,noreferrer");
  };

  const handleResend = (invitation) =>
    runAction(`resend-${invitation.id}`, async () => {
      try {
        const result = await resendInvitation(invitation.id);

        toast.success(
          result.message || `Invitation re-sent to ${invitation.supplier_contact_email}.`
        );

        onChanged?.();
      } catch (error) {
        toast.error(error.message);
      }
    });

  const handleFollowUp = (invitation, mode) =>
    runAction(`${mode}-${invitation.id}`, async () => {
      try {
        const { message } = await createManualFollowUp({
          invitation_id: invitation.id,
          mode,
          send_now: true,
        });

        toast.success(message || "Follow-up sent.");

        onChanged?.();
      } catch (error) {
        toast.error(error.message);
      }
    });

  const confirmCancel = async () => {
    if (!cancelTarget) return;

    try {
      setPending(`cancel-${cancelTarget.id}`);

      await cancelInvitation(cancelTarget.id);

      toast.success(`Invitation for ${cancelTarget.supplier_name} cancelled.`);

      setCancelTarget(null);

      onChanged?.();
    } catch (error) {
      // The API refuses to withdraw an invitation that already has a quote —
      // surface that reason verbatim instead of a generic failure.
      toast.error(error.message);
    } finally {
      setPending(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-4">
        <SummaryTile label="Invited" value={counts.total} />
        <SummaryTile label="Responded" value={counts.responded} tone="success" />
        <SummaryTile label="Awaiting" value={counts.pendingCount} tone="warning" />
        <SummaryTile label="Incomplete" value={counts.incomplete} tone="danger" />
      </div>

      {invitations.length === 0 ? (
        <EmptyState
          title="No suppliers invited yet"
          description="Invite suppliers below — each one receives a private form link, so they never see another supplier's quote."
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-[1180px] w-full text-sm">
              <thead>
                <tr className="border-b border-border-default bg-surface-2 text-left text-xs font-semibold uppercase tracking-wider text-subtle">
                  <th className="px-5 py-3">Supplier</th>
                  <th className="px-5 py-3">Contact</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Sent</th>
                  <th className="px-5 py-3">Reminders</th>
                  <th className="px-5 py-3">Opens</th>
                  <th className="px-5 py-3">Last activity</th>
                  <th className="px-5 py-3">Missing fields</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border-default">
                {invitations.map((invitation) => {
                  const isFocused = focusInvitationId === invitation.id;
                  const missingLabels =
                    invitation.missing_field_labels?.length > 0
                      ? invitation.missing_field_labels
                      : (invitation.missing_fields || []).map((field) =>
                          formatFieldKey(field)
                        );

                  const lastActivity = latestActivity(invitation);

                  return (
                    <tr
                      key={invitation.id}
                      className={`align-top transition ${
                        isFocused
                          ? "bg-primary-soft/40 ring-1 ring-inset ring-primary/30"
                          : "hover:bg-surface-hover"
                      }`}
                    >
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2.5">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-xs font-semibold text-primary-soft-fg">
                            {(invitation.supplier_name || "?").charAt(0).toUpperCase()}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate font-medium text-content">
                              {invitation.supplier_name}
                            </p>
                            {invitation.supplier_contact_name && (
                              <p className="truncate text-xs text-subtle">
                                {invitation.supplier_contact_name}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>

                      <td className="px-5 py-4">
                        <span className="block truncate text-muted">
                          {invitation.supplier_contact_email || "—"}
                        </span>
                        <span className="mt-0.5 block text-xs text-subtle">
                          Risk {invitation.supplier_risk || "low"}
                        </span>
                      </td>

                      <td className="px-5 py-4">
                        <StatusBadge status={invitation.status} domain="invitation" />
                        {invitation.status_reason && (
                          <p className="mt-1.5 max-w-[16rem] text-xs leading-relaxed text-subtle">
                            {invitation.status_reason}
                          </p>
                        )}
                      </td>

                      <td className="whitespace-nowrap px-5 py-4 text-muted">
                        {invitation.last_sent_at
                          ? formatDateTime(invitation.last_sent_at)
                          : "Not sent"}
                      </td>

                      <td className="whitespace-nowrap px-5 py-4">
                        <span className="text-muted">
                          {formatNumber(invitation.reminder_count)}
                        </span>
                        {invitation.next_reminder_at && (
                          <span className="mt-0.5 block text-xs text-subtle">
                            Next {formatRelativeTime(invitation.next_reminder_at)}
                          </span>
                        )}
                      </td>

                      <td className="whitespace-nowrap px-5 py-4 text-muted">
                        {formatNumber(invitation.view_count)}
                      </td>

                      <td className="whitespace-nowrap px-5 py-4 text-muted">
                        {lastActivity ? (
                          <span title={formatDateTime(lastActivity)}>
                            {formatRelativeTime(lastActivity)}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>

                      <td className="px-5 py-4">
                        {missingLabels.length === 0 ? (
                          <span className="text-subtle">—</span>
                        ) : (
                          <div className="flex flex-wrap gap-1.5">
                            {missingLabels.map((label) => (
                              <span
                                key={label}
                                className="rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-medium text-warning-soft-fg"
                              >
                                {label}
                              </span>
                            ))}
                          </div>
                        )}

                        {invitation.blocking_question && (
                          <p className="mt-2 max-w-[16rem] text-xs leading-relaxed text-subtle">
                            {invitation.blocking_question}
                          </p>
                        )}
                      </td>

                      <td className="px-5 py-4">
                        <div className="flex flex-wrap items-center justify-end gap-1.5">
                          <RowAction
                            label="Copy link"
                            busy={pending === `copy-${invitation.id}`}
                            onClick={() => handleCopyLink(invitation)}
                          />
                          <RowAction
                            label="Open form"
                            onClick={() => handleOpenForm(invitation)}
                          />
                          <RowAction
                            label="Resend link"
                            busy={pending === `resend-${invitation.id}`}
                            onClick={() => handleResend(invitation)}
                          />
                          <RowAction
                            label="Send reminder"
                            busy={pending === `reminder-${invitation.id}`}
                            onClick={() => handleFollowUp(invitation, "reminder")}
                          />

                          {/* Only meaningful when the quote exists but is missing fields. */}
                          {invitation.status === "incomplete" && (
                            <RowAction
                              label="Chase missing fields"
                              tone="warning"
                              busy={pending === `incomplete-${invitation.id}`}
                              onClick={() => handleFollowUp(invitation, "incomplete")}
                            />
                          )}

                          <RowAction
                            label="Cancel"
                            tone="danger"
                            busy={pending === `cancel-${invitation.id}`}
                            onClick={() => setCancelTarget(invitation)}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="border-t border-border-default bg-surface-2 px-5 py-3">
            <p className="text-xs text-muted">
              Every reminder is drafted against this supplier only, and the link
              stays the same — resending never invalidates a link already shared.
            </p>
          </div>
        </Card>
      )}

      <InviteSuppliersPanel
        rfqId={rfqId}
        invitations={invitations}
        onChanged={onChanged}
      />

      <ConfirmModal
        isOpen={Boolean(cancelTarget)}
        onClose={() => setCancelTarget(null)}
        onConfirm={confirmCancel}
        title="Cancel invitation"
        description={`Withdraw the invitation for "${cancelTarget?.supplier_name}"? Their link stops working immediately and they will not be chased again.`}
        confirmText="Cancel invitation"
        cancelText="Keep invitation"
        isLoading={pending === `cancel-${cancelTarget?.id}`}
      />
    </div>
  );
}

/** The most recent thing that happened on an invitation, from whatever timestamps exist. */
function latestActivity(invitation) {
  const candidates = [
    invitation.responded_at,
    invitation.first_viewed_at,
    invitation.last_reminder_at,
    invitation.last_sent_at,
    invitation.sent_at,
  ].filter(Boolean);

  if (candidates.length === 0) return null;

  return candidates.reduce((latest, value) =>
    new Date(value) > new Date(latest) ? value : latest
  );
}

const TILE_TONES = {
  neutral: "text-content",
  success: "text-success-soft-fg",
  warning: "text-warning-soft-fg",
  danger: "text-danger-soft-fg",
};

function SummaryTile({ label, value, tone = "neutral" }) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wider text-subtle">
        {label}
      </p>
      <p className={`mt-1 text-xl font-bold ${TILE_TONES[tone]}`}>
        {formatNumber(value)}
      </p>
    </Card>
  );
}

function RowAction({ label, onClick, busy = false, tone = "neutral" }) {
  const tones = {
    neutral: "text-muted hover:bg-surface-2 hover:text-content",
    warning: "text-warning-soft-fg hover:bg-warning-soft",
    danger: "text-danger-soft-fg hover:bg-danger-soft",
  };

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      loading={busy}
      onClick={onClick}
      className={`px-2.5 py-1.5 text-xs ${tones[tone]}`}
    >
      {label}
    </Button>
  );
}

export default InvitationsTab;
