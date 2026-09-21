import EmptyState from "@/shared/components/EmptyState";
import { StatusBadge } from "@/shared/components/StatusBadge";
import { Card } from "@/shared/components/ui";
import { formatDateTime, formatNumber } from "@/shared/lib/format";

/**
 * Who was invited, and what came back.
 *
 * A deliberately small read-only table of its own rather than the buyer's
 * `InvitationsTab`: that component owns its own requests (it fetches, it
 * resends, it copies a form link), and reusing it would mean either firing calls
 * the demo is not allowed to make or neutering a screen whose whole purpose is
 * those controls. Five columns of payload is the honest version of what a visitor
 * needs here.
 *
 * The invitation's `form_link`/`token` is deliberately not rendered: it is a
 * secret, and a public demo page is the last place to publish one — even the
 * demo's own placeholder token.
 */

function Cell({ children }) {
  return <td className="px-5 py-4 align-top">{children}</td>;
}

function DemoInvitationList({ invitations = [] }) {
  if (!invitations.length) {
    return (
      <EmptyState
        title="No suppliers were invited in this sample"
        description="Invitations appear here as soon as a supplier is asked to quote."
      />
    );
  }

  const responded = invitations.filter((invitation) => invitation.quote_id != null).length;

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] text-sm">
          <thead>
            <tr className="border-b border-border-default bg-surface-2 text-left text-xs font-semibold uppercase tracking-wider text-subtle">
              <th className="px-5 py-3">Supplier</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Last sent</th>
              <th className="px-5 py-3">Reminders</th>
              <th className="px-5 py-3">Opens</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-border-default">
            {invitations.map((invitation) => (
              <tr key={invitation.id} className="align-top">
                <Cell>
                  <div className="font-medium text-content">
                    {invitation.supplier_name || "Unknown supplier"}
                  </div>

                  {invitation.supplier_contact_name && (
                    <div className="mt-0.5 text-xs text-subtle">
                      {invitation.supplier_contact_name}
                    </div>
                  )}
                </Cell>

                <Cell>
                  <StatusBadge status={invitation.status} domain="invitation" />

                  {invitation.status_reason && (
                    <p className="mt-2 max-w-[16rem] text-xs leading-relaxed text-subtle">
                      {invitation.status_reason}
                    </p>
                  )}
                </Cell>

                <Cell>
                  <span className="whitespace-nowrap text-muted">
                    {formatDateTime(invitation.last_sent_at)}
                  </span>
                </Cell>

                <Cell>
                  <span className="text-muted">
                    {formatNumber(invitation.reminder_count)}
                  </span>
                </Cell>

                <Cell>
                  <span className="text-muted">
                    {formatNumber(invitation.view_count)}
                  </span>
                </Cell>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-border-default bg-surface-2 px-5 py-3">
        <p className="text-xs leading-relaxed text-muted">
          {invitations.length} contractors were invited and {responded} responded. Suppliers need no
          account — each one opens a private form link, and the buyer sees who has
          opened it.
        </p>
      </div>
    </Card>
  );
}

export default DemoInvitationList;
