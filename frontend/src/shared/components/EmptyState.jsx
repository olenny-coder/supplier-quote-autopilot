function EmptyState({
  title = "No data found",
  description = "There is nothing to display.",
  icon,
  action = null,
}) {
  return (
    <div className="flex w-full flex-col items-center justify-center rounded-2xl border border-dashed border-border-strong bg-surface px-8 py-20 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-soft text-primary-soft-fg">
        {icon || (
          <svg
            className="h-7 w-7"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        )}
      </div>
      <h2 className="text-base font-semibold text-content">{title}</h2>
      <p className="mt-1.5 max-w-xs text-sm leading-relaxed text-muted">
        {description}
      </p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export default EmptyState;
