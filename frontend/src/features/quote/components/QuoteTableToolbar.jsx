function QuoteTableToolbar({ query, setQuery, total, visible }) {
  return (
    <div className="flex flex-col gap-3 border-b border-border-default bg-surface-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="relative w-full sm:max-w-xs">
        <svg
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z"
          />
        </svg>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search supplier, terms, remarks…"
          aria-label="Search quotes"
          className="w-full rounded-lg border border-border-default bg-surface py-2 pl-9 pr-8 text-sm text-content placeholder:text-subtle transition focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/50"
        />

        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            aria-label="Clear search"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-subtle transition hover:text-content"
          >
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>

      <p className="text-xs text-muted">
        {visible === total
          ? `${total} ${total === 1 ? "quote" : "quotes"}`
          : `${visible} of ${total} quotes`}
      </p>
    </div>
  );
}

export default QuoteTableToolbar;
