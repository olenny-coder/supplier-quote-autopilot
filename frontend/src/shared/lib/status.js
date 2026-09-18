/**
 * The single source of truth for "status string → badge colour".
 *
 * Status strings come from several domains (RFQ lifecycle, invitation,
 * completeness, follow-up delivery, approval decision, supplier risk) and some
 * words mean different things in different domains — `rejected` is a refused
 * award in the approval domain but a discarded draft in the follow-up domain.
 * So the *colour* is decided once, globally, by `VARIANTS`, and a domain may
 * only override the label (and, rarely, the colour) through
 * `DOMAIN_OVERRIDES`. Pages must use `getStatusBadge()` or the `<StatusBadge />`
 * component from `shared/components/StatusBadge` instead of inventing their own
 * colour per screen.
 *
 * This module stays JSX-free on purpose: it is imported by plain `.js` feature
 * modules (hooks, form config) as well as by components.
 */

const DEFAULT_VARIANT = "neutral";

//: status -> Badge variant. Every status the buyer API can return.
const VARIANTS = {
  // RFQ lifecycle
  draft: "neutral",
  open: "primary",
  closed: "neutral",
  awarded: "success",
  cancelled: "danger",

  // Invitation lifecycle
  pending: "warning",
  submitted: "success",
  incomplete: "warning",
  expired: "danger",
  declined: "danger",

  // Quote completeness
  complete: "success",

  // Follow-up delivery
  queued: "primary",
  sent: "success",
  failed: "danger",
  rejected: "danger",
  skipped: "neutral",

  // Approval decision
  approved: "success",
  deferred: "warning",

  // Supplier risk rating
  low: "success",
  medium: "warning",
  high: "danger",
};

const LABELS = {
  draft: "Draft",
  open: "Open",
  closed: "Closed",
  awarded: "Awarded",
  cancelled: "Cancelled",
  pending: "Awaiting response",
  submitted: "Responded",
  incomplete: "Incomplete",
  expired: "Expired",
  declined: "Declined",
  complete: "Complete",
  queued: "Queued",
  sent: "Sent",
  failed: "Failed",
  rejected: "Rejected",
  skipped: "Skipped",
  approved: "Approved",
  deferred: "Deferred",
  low: "Low risk",
  medium: "Medium risk",
  high: "High risk",
};

const DOMAIN_OVERRIDES = {
  rfq: {},
  invitation: {},
  quote: {},
  risk: {},
  approval: {
    approved: { label: "Approved", variant: "success" },
    rejected: { label: "Rejected", variant: "danger" },
    deferred: { label: "Deferred", variant: "warning" },
  },
  followup: {
    draft: { label: "Draft", variant: "warning" },
    queued: { label: "Queued for approval", variant: "primary" },
    rejected: { label: "Discarded", variant: "neutral" },
    sent: { label: "Sent", variant: "success" },
  },
};

/** "no_response" -> "No response". Fallback for statuses not in the maps. */
function humanise(value) {
  if (!value) return "Unknown";

  const text = String(value).replace(/[_-]+/g, " ").trim();

  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Resolve a status to `{ label, variant }`.
 *
 * @param {string} status  raw status from the API
 * @param {"rfq"|"invitation"|"quote"|"approval"|"followup"|"risk"} [domain]
 *        optional domain, for label nuance only
 */
export function getStatusBadge(status, domain) {
  const override = domain ? DOMAIN_OVERRIDES[domain]?.[status] : undefined;

  return {
    label: override?.label || LABELS[status] || humanise(status),
    variant: override?.variant || VARIANTS[status] || DEFAULT_VARIANT,
  };
}

export function getStatusLabel(status, domain) {
  return getStatusBadge(status, domain).label;
}

//: Follow-up *kind* (why a message exists) is orthogonal to its delivery status,
//: so it gets its own small map rather than sharing the status colours.
const FOLLOWUP_KIND_BADGES = {
  no_response: { label: "No response", variant: "warning" },
  incomplete_quote: { label: "Incomplete quote", variant: "warning" },
  deadline_warning: { label: "Deadline warning", variant: "primary" },
  manual: { label: "Manual", variant: "primary" },
};

export function getFollowUpKindBadge(kind) {
  return (
    FOLLOWUP_KIND_BADGES[kind] || {
      label: humanise(kind),
      variant: DEFAULT_VARIANT,
    }
  );
}

//: Options for the RFQ status <select> (create/edit forms and list filters).
export const RFQ_STATUS_OPTIONS = [
  { value: "draft", label: "Draft" },
  { value: "open", label: "Open" },
  { value: "closed", label: "Closed" },
  { value: "awarded", label: "Awarded" },
  { value: "cancelled", label: "Cancelled" },
];

//: Options for the supplier risk <select>.
export const RISK_RATING_OPTIONS = [
  { value: "low", label: "Low risk" },
  { value: "medium", label: "Medium risk" },
  { value: "high", label: "High risk" },
];
