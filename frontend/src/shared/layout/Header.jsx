import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import ThemeToggle from "@/shared/theme/ThemeToggle";

import { useAuth } from "@/features/auth/useAuth";

const NAV_ITEMS = [
  { label: "Dashboard", to: "/" },
  { label: "RFQs", to: "/rfqs" },
  { label: "Suppliers", to: "/suppliers" },
];

/**
 * Top navigation for the authenticated shell: wordmark, the three buyer
 * sections, the theme toggle and the account menu.
 *
 * The nav renders twice on purpose — inline on ≥sm and as a horizontally
 * scrollable strip under the bar on phones, where the wordmark plus three
 * links plus the account menu will not fit on one line.
 */
function Header() {
  const location = useLocation();
  const { user, logout } = useAuth();

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Close the account menu on an outside click or Escape, matching Modal.
  useEffect(() => {
    if (!menuOpen) return undefined;

    const handlePointerDown = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    };

    const handleKeyDown = (event) => {
      if (event.key === "Escape") setMenuOpen(false);
    };

    document.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen]);

  // `/` is only active on an exact match; the others stay active on sub-routes
  // so /rfqs/12 still highlights RFQs.
  const isActive = (to) =>
    to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);

  const accountLabel = user?.company_name || user?.email || "Buyer account";
  const accountSubLabel = user?.email || "";

  const navLinkClass = (to) =>
    `rounded-lg px-3.5 py-1.5 text-sm font-medium transition whitespace-nowrap ${
      isActive(to)
        ? "bg-surface text-content shadow-sm"
        : "text-muted hover:text-content"
    }`;

  return (
    <header className="sticky top-0 z-40 border-b border-border-default bg-surface/80 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-5 sm:px-6">
        <div className="flex h-16 items-center justify-between gap-4">
          <Link to="/" className="flex min-w-0 items-center gap-2.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-primary to-violet-500 shadow-lg shadow-primary/25">
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
            <span className="flex min-w-0 flex-col leading-none">
              <span className="truncate text-sm font-semibold tracking-tight text-content">
                Supplier Quote Autopilot
              </span>
              <span className="mt-1 hidden text-[11px] font-medium text-subtle sm:block">
                RFQ collection &amp; quote analysis
              </span>
            </span>
          </Link>

          <div className="flex items-center gap-2 sm:gap-3">
            <nav className="hidden items-center gap-1 rounded-xl border border-border-default bg-surface-2 p-1 sm:flex">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={navLinkClass(item.to)}
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <ThemeToggle />

            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((prev) => !prev)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                className="flex max-w-[10rem] items-center gap-2 rounded-xl border border-border-default bg-surface px-2.5 py-2 text-sm font-medium text-content transition hover:border-border-strong hover:bg-surface-hover sm:max-w-xs"
              >
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-[11px] font-semibold text-primary-soft-fg">
                  {(accountLabel || "?").charAt(0).toUpperCase()}
                </span>
                <span className="hidden truncate sm:inline">{accountLabel}</span>
                <svg
                  className={`h-3.5 w-3.5 shrink-0 text-subtle transition ${
                    menuOpen ? "rotate-180" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              {menuOpen && (
                <div
                  role="menu"
                  className="animate-pop-in absolute right-0 mt-2 w-64 overflow-hidden rounded-2xl border border-border-default bg-surface shadow-pop"
                >
                  <div className="border-b border-border-default px-4 py-3">
                    <p className="truncate text-sm font-semibold text-content">
                      {accountLabel}
                    </p>
                    {accountSubLabel && (
                      <p className="mt-0.5 truncate text-xs text-muted">
                        {accountSubLabel}
                      </p>
                    )}
                    {user?.full_name && (
                      <p className="mt-1 truncate text-xs text-subtle">
                        {user.full_name}
                      </p>
                    )}
                  </div>

                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      logout();
                    }}
                    className="flex w-full items-center gap-2.5 px-4 py-3 text-left text-sm font-medium text-muted transition hover:bg-danger-soft hover:text-danger-soft-fg"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                      />
                    </svg>
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Phone layout: the same three destinations, on their own line. */}
        <nav className="flex items-center gap-1 overflow-x-auto pb-2 sm:hidden">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`${navLinkClass(item.to)} bg-surface-2`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

export default Header;
