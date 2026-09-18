import { Link, useLocation } from "react-router-dom";

import ThemeToggle from "@/shared/theme/ThemeToggle";

function Header() {
  const location = useLocation();

  const navItems = [
    { label: "RFQs", to: "/" },
    { label: "New RFQ", to: "/rfqs/new" },
  ];

  const isActive = (to) =>
    to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);

  return (
    <header className="sticky top-0 z-40 border-b border-border-default bg-surface/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-5 sm:px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-linear-to-br from-primary to-violet-500 shadow-lg shadow-primary/25">
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
              RFQ Comparison
            </span>
            <span className="mt-1 hidden text-[11px] font-medium text-subtle sm:block">
              Supplier quote analysis
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-2 sm:gap-3">
          <nav className="hidden items-center gap-1 rounded-xl border border-border-default bg-surface-2 p-1 sm:flex">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
                  isActive(item.to)
                    ? "bg-surface text-content shadow-sm"
                    : "text-muted hover:text-content"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

export default Header;
