import client from "@/shared/api/client";

/**
 * Dashboard feature — the buyer's landing page.
 *
 * One call returns every counter plus the two working lists, so the page has a
 * single loading state instead of fanning out across features:
 *
 *   GET /dashboard/summary -> {
 *     rfqs_total, rfqs_open, rfqs_awaiting_approval, rfqs_awarded,
 *     suppliers_total,
 *     invitations_total, invitations_pending, invitations_submitted,
 *     invitations_incomplete, invitations_expired,
 *     quotes_total, quotes_complete,
 *     followups_total, followups_pending_approval, followups_sent,
 *     followups_failed,
 *     deadlines_soon: [{rfq_id, rfq_number, item_name, deadline, hours_left,
 *                       overdue, pending_suppliers, incomplete_suppliers}],
 *     needs_attention: [{invitation_id, rfq_id, rfq_number, supplier_name,
 *                        status, missing_fields, reminder_count,
 *                        next_reminder_at, reason}],
 *     ai_available, auto_send_followups
 *   }
 */

export const getSummary = async () => {
  const response = await client.get("/dashboard/summary");
  return response.data;
};
