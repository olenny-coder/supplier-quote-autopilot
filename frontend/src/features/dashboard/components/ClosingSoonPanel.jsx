import { Link } from "react-router-dom";

import EmptyState from "@/shared/components/EmptyState";
import { Badge, Card } from "@/shared/components/ui";
import { buttonClass } from "@/shared/lib/button";
import { formatDate, formatHoursRemaining, formatNumber } from "@/shared/lib/format";

/**
 * "Closing soon" — requests whose quote deadline falls inside the server's
 * warning window, nearest first (the API already sorts them). Overdue deadlines
 * are flagged in red, because those are the ones that need a decision today —
 * on a maintenance job the works still have to be scheduled after the award.
 */
function ClosingSoonPanel({ deadlines = [] }) {
  return (
    <Card className="flex flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-border-default bg-surface-2/50 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-content">Closing soon</h2>
          <p className="mt-0.5 text-xs text-muted">
            Quote deadlines inside the warning window
          </p>
        </div>

        {deadlines.length > 0 && (
          <span className="rounded-full bg-surface-2 px-2.5 py-0.5 text-xs font-semibold text-muted">
            {formatNumber(deadlines.length)}
          </span>
        )}
      </div>

      {deadlines.length === 0 ? (
        <div className="p-5">
          <EmptyState
            title="No deadlines imminent"
            description="Nothing is due in the next few days. Open requests will appear here as their deadlines approach."
          />
        </div>
      ) : (
        <ul className="divide-y divide-border-default">
          {deadlines.map((item) => (
            <li
              key={item.rfq_id}
              className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={`/rfqs/${item.rfq_id}?tab=suppliers`}
                    className="truncate text-sm font-semibold text-content transition hover:text-primary"
                  >
                    {item.item_name}
                  </Link>
                  <Badge variant="neutral">{item.rfq_number}</Badge>
                </div>

                <p className="mt-1.5 text-xs text-muted">
                  Deadline {formatDate(item.deadline)} ·{" "}
                  {formatNumber(item.pending_suppliers)} pending ·{" "}
                  {formatNumber(item.incomplete_suppliers)} incomplete
                </p>
              </div>

              <div className="flex shrink-0 items-center gap-3">
                <span
                  className={`text-sm font-semibold ${
                    item.overdue ? "text-danger" : "text-muted"
                  }`}
                >
                  {formatHoursRemaining(item.hours_left)}
                </span>

                <Link
                  to={`/rfqs/${item.rfq_id}?tab=suppliers`}
                  className={buttonClass("outline", "sm")}
                >
                  Chase
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default ClosingSoonPanel;
