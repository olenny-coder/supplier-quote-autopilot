/*
 * The assistant's mark — a friendly bot/robot head so the launcher reads as an
 * AI agent rather than a generic chat bubble. Inherits color via currentColor.
 */
function AgentIcon({ className = "h-6 w-6" }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {/* antenna */}
      <line x1="12" y1="7" x2="12" y2="4.5" />
      <circle cx="12" cy="3.1" r="1.15" fill="currentColor" stroke="none" />
      {/* head */}
      <rect x="4" y="7" width="16" height="12" rx="3.5" />
      {/* ears */}
      <line x1="2" y1="13" x2="2" y2="15.5" />
      <line x1="22" y1="13" x2="22" y2="15.5" />
      {/* eyes */}
      <line x1="9" y1="12" x2="9" y2="14.5" />
      <line x1="15" y1="12" x2="15" y2="14.5" />
    </svg>
  );
}

export default AgentIcon;
