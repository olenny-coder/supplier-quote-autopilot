import { Link } from "react-router-dom";

/**
 * Shared shell for the public auth screens: a branded panel on the left for
 * wide viewports and the form itself on the right. Sign-in and registration
 * are the only routes outside the app shell (header/footer/chat), so they need
 * their own minimal layout.
 */
function AuthLayout({ title, subtitle, footer, children }) {
  return (
    <div className="theme-transition flex min-h-screen flex-col text-content lg:flex-row">
      {/* Brand panel — decorative, hidden on small screens to keep the form above the fold. */}
      <aside className="relative hidden overflow-hidden border-r border-border-default bg-surface lg:flex lg:w-[46%] lg:flex-col lg:justify-between lg:p-12">
        <span className="pointer-events-none absolute inset-0 bg-linear-to-br from-primary/12 via-transparent to-violet-500/12" />

        <Link to="/" className="relative flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-linear-to-br from-primary to-violet-500 shadow-lg shadow-primary/25">
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
              />
            </svg>
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-sm font-semibold tracking-tight text-content">
              Supplier Quote Autopilot
            </span>
            <span className="mt-1 text-[11px] font-medium text-subtle">
              RFQ collection &amp; quote analysis
            </span>
          </span>
        </Link>

        <div className="relative max-w-md">
          <h2 className="text-2xl font-bold tracking-tight text-content">
            Collect every quote. Award with the evidence in front of you.
          </h2>
          <ul className="mt-6 space-y-3 text-sm text-muted">
            {[
              "One private form link per supplier — no logins for them.",
              "Land cost normalisation across currency and Incoterms.",
              "Reminders and chasers queued for your approval.",
              "A signed audit entry for every award decision.",
            ].map((item) => (
              <li key={item} className="flex items-start gap-2.5">
                <span className="mt-1.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-soft-fg">
                  <svg
                    className="h-2.5 w-2.5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-subtle">
          No supplier is awarded automatically — the buyer decides.
        </p>
      </aside>

      <main className="flex flex-1 items-center justify-center px-5 py-12 sm:px-8">
        <div className="w-full max-w-md">
          <Link to="/" className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-linear-to-br from-primary to-violet-500 shadow-lg shadow-primary/25">
              <svg
                className="h-5 w-5 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                />
              </svg>
            </span>
            <span className="text-sm font-semibold tracking-tight text-content">
              Supplier Quote Autopilot
            </span>
          </Link>

          <h1 className="text-2xl font-bold tracking-tight text-content sm:text-3xl">
            {title}
          </h1>
          {subtitle && <p className="mt-2 text-sm text-muted">{subtitle}</p>}

          <div className="mt-8">{children}</div>

          {footer && <div className="mt-6 text-sm text-muted">{footer}</div>}
        </div>
      </main>
    </div>
  );
}

export default AuthLayout;
