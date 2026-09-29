import { Link } from "react-router-dom";

import { LogoBadge } from "@/shared/components/Logo";

/**
 * Shared shell for the public auth screens: a branded panel on the left for
 * wide viewports and the form itself on the right. Sign-in and registration
 * are the only routes outside the app shell (header/footer/chat), so they need
 * their own minimal layout.
 *
 * The panel's type scale is deliberately larger than the app shell's. It is a
 * full-height column at 46% of the viewport, not a 64 px bar, so the wordmark at
 * the header's 14 px read as a caption on a page of empty space. The wordmark,
 * tagline and headline step up together (18/20 · 12 · 30 px) and the mark grows to
 * 44 px to match, which is the same lockup the header uses at bar scale.
 */
function AuthLayout({ title, subtitle, footer, children }) {
  return (
    <div className="theme-transition flex min-h-screen flex-col text-content lg:flex-row">
      {/* Brand panel — decorative, hidden on small screens to keep the form above the fold. */}
      <aside className="relative hidden overflow-hidden border-r border-border-default bg-surface lg:flex lg:w-[46%] lg:flex-col lg:justify-between lg:p-12">
        <span className="pointer-events-none absolute inset-0 bg-linear-to-br from-primary/12 via-transparent to-violet-500/12" />

        <Link to="/" className="relative flex items-center gap-3.5">
          <LogoBadge size={44} />
          <span className="flex flex-col">
            <span className="text-lg font-semibold leading-tight tracking-tight text-content sm:text-xl">
              Supplier Quote Autopilot
            </span>
            <span className="mt-1.5 text-xs font-medium tracking-wide text-subtle">
              Building services procurement
            </span>
          </span>
        </Link>

        <div className="relative max-w-md">
          <h2 className="text-2xl font-bold leading-snug tracking-tight text-content xl:text-3xl">
            Collect every quote. Award with the evidence in front of you.
          </h2>
          <ul className="mt-6 space-y-3 text-sm leading-relaxed text-muted">
            {[
              "One private form link per contractor — no logins for them.",
              "Rates, response times and licences normalised side by side.",
              "Reminders and chasers queued for your approval.",
              "A signed audit entry for every award decision.",
            ].map((item) => (
              <li key={item} className="flex items-start gap-2.5">
                <span className="mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary-soft-fg">
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
          <Link to="/" className="mb-8 flex items-center gap-2.5 lg:hidden">
            <LogoBadge size={40} />
            <span className="text-base font-semibold tracking-tight text-content">
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
