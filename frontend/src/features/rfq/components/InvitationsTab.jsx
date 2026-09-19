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
        <Card className="hidden overflow-hidden md:block">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1360px] text-sm">
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
                  <th className="w-[26rem] px-5 py-3 text-right">Actions</th>
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

                      <td className="px-5 py-4 align-top">
                        {/*
                          A fixed 3x2 GRID, not a wrapping flex row.

                          With `flex flex-wrap justify-end` the buttons had
                          intrinsic widths and each row wrapped at a different
                          point — "Chase missing fields" exists only on an
                          incomplete row, so that row pushed a button onto a second
                          line while its neighbours did not. Right-aligned, the
                          result was a column that visibly zig-zagged down the
                          table and never lined up with the row above it.

                          A grid with `w-full` buttons pins every action to the
                          same cell in every row. The conditional slot keeps its
                          empty cell rather than being skipped, so Cancel — the
                          destructive one — is always in the same place and cannot
                          be mis-clicked because a neighbour grew by a button.
                        */}
                        <div className="grid w-[26rem] grid-cols-3 gap-1.5">
                          <RowAction
                            compact
                            label="Copy link"
                            busy={pending === `copy-${invitation.id}`}
                            onClick={() => handleCopyLink(invitation)}
                          />
                          <RowAction
                            compact
                            label="Open form"
                            onClick={() => handleOpenForm(invitation)}
                          />
                          <RowAction
                            compact
                            label="Resend link"
                            busy={pending === `resend-${invitation.id}`}
                            onClick={() => handleResend(invitation)}
                          />
                          <RowAction
                            compact
                            label="Send reminder"
                            busy={pending === `reminder-${invitation.id}`}
                            onClick={() => handleFollowUp(invitation, "reminder")}
                          />

                          {/* Only meaningful when the quote exists but is missing fields. */}
                          {invitation.status === "incomplete" ? (
                            <RowAction
                              compact
                              label="Chase fields"
                              tone="warning"
                              busy={pending === `incomplete-${invitation.id}`}
                              onClick={() => handleFollowUp(invitation, "incomplete")}
                            />
                          ) : (
                            <span aria-hidden="true" />
                          )}

                          <RowAction
                            compact
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

      {/*
        Phones get one card per supplier instead of the table.

        The table is 1360px wide and scrolls, which is the right compromise for a
        grid of numbers — but not for this one. The actions are the whole point of
        the screen, and reaching them meant scrolling the row sideways until the
        supplier's name was off-screen, so you lost track of which supplier you
        were about to email. A card keeps the name, the status and every action
        together on one screen.
      */}
      {invitations.length > 0 && (
        <div className="space-y-3 md:hidden">
          {invitations.map((invitation) => (
            <InvitationCard
              key={invitation.id}
              invitation={invitation}
              isFocused={focusInvitationId === invitation.id}
              pending={pending}
              onCopyLink={() => handleCopyLink(invitation)}
              onOpenForm={() => handleOpenForm(invitation)}
              onResend={() => handleResend(invitation)}
              onFollowUp={handleFollowUp}
              onCancel={() => setCancelTarget(invitation)}
            />
          ))}
        </div>
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

/**
 * One supplier, as a card, for screens too narrow for the table.
 *
 * Carries the same information in the same order as the table row, so switching
 * between a laptop and a phone is not a re-learning exercise.
 */
function InvitationCard({
  invitation,
  isFocused,
  pending,
  onCopyLink,
  onOpenForm,
  onResend,
  onFollowUp,
  onCancel,
}) {
  const missingLabels =
    invitation.missing_field_labels?.length > 0
      ? invitation.missing_field_labels
      : (invitation.missing_fields || []).map((field) => formatFieldKey(field));

  const lastActivity = latestActivity(invitation);

  return (
    <Card
      className={`p-4 ${
        isFocused ? "ring-1 ring-inset ring-primary/30" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-sm font-semibold text-primary-soft-fg">
          {(invitation.supplier_name || "?").charAt(0).toUpperCase()}
        </span>

        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-content">
            {invitation.supplier_name}
          </p>
          {/* A long address must wrap rather than widen the card. */}
          <p className="break-words text-sm text-muted">
            {invitation.supplier_contact_email || "—"}
          </p>
          {invitation.supplier_contact_name && (
            <p className="truncate text-xs text-subtle">
              {invitation.supplier_contact_name}
            </p>
          )}
        </div>

        <StatusBadge status={invitation.status} domain="invitation" />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <CardFact label="Sent">
          {invitation.last_sent_at
            ? formatDateTime(invitation.last_sent_at)
            : "Not sent"}
        </CardFact>
        <CardFact label="Reminders">
          {formatNumber(invitation.reminder_count)}
          {invitation.next_reminder_at
            ? ` · next ${formatRelativeTime(invitation.next_reminder_at)}`
            : ""}
        </CardFact>
        <CardFact label="Opens">{formatNumber(invitation.view_count)}</CardFact>
        <CardFact label="Last activity">
          {lastActivity ? formatRelativeTime(lastActivity) : "—"}
        </CardFact>
        <CardFact label="Risk">{invitation.supplier_risk || "low"}</CardFact>
      </dl>

      {invitation.status_reason && (
        <p className="mt-3 text-xs leading-relaxed text-subtle">
          {invitation.status_reason}
        </p>
      )}

      {missingLabels.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium uppercase tracking-wider text-subtle">
            Missing fields
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {missingLabels.map((label) => (
              <span
                key={label}
                className="rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-medium text-warning-soft-fg"
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      )}

      {invitation.blocking_question && (
        <p className="mt-3 text-xs leading-relaxed text-subtle">
          {invitation.blocking_question}
        </p>
      )}

      {/*
        Two columns rather than a scrolling row: every button is a full 44px tall
        so it is a real thumb target, and Cancel keeps the last cell on its own so
        it is never adjacent to the action a buyer meant to press.
      */}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <RowAction
          label="Copy link"
          busy={pending === `copy-${invitation.id}`}
          onClick={onCopyLink}
        />
        <RowAction label="Open form" onClick={onOpenForm} />
        <RowAction
          label="Resend link"
          busy={pending === `resend-${invitation.id}`}
          onClick={onResend}
        />
        <RowAction
          label="Send reminder"
          busy={pending === `reminder-${invitation.id}`}
          onClick={() => onFollowUp(invitation, "reminder")}
        />

        {invitation.status === "incomplete" && (
          <RowAction
            label="Chase fields"
            tone="warning"
            busy={pending === `incomplete-${invitation.id}`}
            onClick={() => onFollowUp(invitation, "incomplete")}
          />
        )}

        <RowAction
          label="Cancel"
          tone="danger"
          busy={pending === `cancel-${invitation.id}`}
          onClick={onCancel}
        />
      </div>
    </Card>
  );
}

function CardFact({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium uppercase tracking-wider text-subtle">
        {label}
      </dt>
      <dd className="truncate text-muted">{children}</dd>
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

/**
 * One row action.
 *
 * `compact` is the dense form used inside the table, where the column is a fixed
 * width and every button must fill its grid cell so the rows line up. The default
 * form is for the phone card, where a button is a thumb target: full width of its
 * cell, at least 44px tall, and never smaller than the readable text size.
 */
function RowAction({ label, onClick, busy = false, tone = "neutral", compact = false }) {
  const tones = {
    neutral: "text-muted hover:bg-surface-2 hover:text-content",
    warning: "text-warning-soft-fg hover:bg-warning-soft",
    danger: "text-danger-soft-fg hover:bg-danger-soft",
  };

  const sizing = compact
    ? "w-full whitespace-nowrap px-2.5 py-1.5 text-xs"
    : "w-full min-h-11 whitespace-nowrap px-3 py-2.5 text-sm";

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      loading={busy}
      onClick={onClick}
      className={`${sizing} ${tones[tone]}`}
    >
      {label}
    </Button>
  );
}

export default InvitationsTab;
