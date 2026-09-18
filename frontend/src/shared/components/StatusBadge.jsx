import { Badge } from "@/shared/components/ui";
import { getFollowUpKindBadge, getStatusBadge } from "@/shared/lib/status";

/**
 * Badges that render the shared status vocabulary from `shared/lib/status`.
 *
 * Kept in their own `.jsx` module (rather than alongside the mapping) so the
 * mapping stays importable from plain `.js` code — hooks, form configuration —
 * without JSX in the module graph.
 */

/** Status badge. Pass `domain` for label nuance (`followup`, `approval`, …). */
export function StatusBadge({ status, domain, className = "" }) {
  const { label, variant } = getStatusBadge(status, domain);

  return (
    <Badge variant={variant} className={className}>
      {label}
    </Badge>
  );
}

/** Supplier risk rating (low / medium / high). */
export function RiskBadge({ rating, className = "" }) {
  return <StatusBadge status={rating || "low"} domain="risk" className={className} />;
}

/** Why a follow-up exists: no response, incomplete quote, deadline, manual. */
export function FollowUpKindBadge({ kind, className = "" }) {
  const { label, variant } = getFollowUpKindBadge(kind);

  return (
    <Badge variant={variant} className={className}>
      {label}
    </Badge>
  );
}
