import { useTheme } from "@/theme/ThemeProvider";

/**
 * Header theme switch.
 *
 * Same control as the buyer app's (`../../frontend/src/shared/theme/
 * ThemeToggle.jsx`) — `role="switch"` with `aria-checked`, a sun and a moon that
 * cross-fade, and an `aria-label` that names the action rather than the state —
 * with one deliberate difference: it is 44x44 px here instead of 36x36.
 *
 * This page is opened from an email on a phone, often one-handed, so the toggle
 * meets the same 44 px minimum tap target as every other control on the form. It
 * is bordered and muted so it reads as a utility control and never competes with
 * the buyer's name and the RFQ summary beside it.
 */
export default function ThemeToggle({ className = "" }) {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className={`group relative inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border-default bg-surface-2 text-muted transition-colors hover:border-border-strong hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${className}`}
    >
      <span className="sr-only">Toggle theme</span>

      {/* Sun */}
      <svg
        className={`absolute h-[18px] w-[18px] transition-all duration-300 ${
          isDark
            ? "rotate-90 scale-0 opacity-0"
            : "rotate-0 scale-100 opacity-100"
        }`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="4" />
        <path
          strokeLinecap="round"
          d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
        />
      </svg>

      {/* Moon */}
      <svg
        className={`absolute h-[18px] w-[18px] transition-all duration-300 ${
          isDark
            ? "rotate-0 scale-100 opacity-100"
            : "-rotate-90 scale-0 opacity-0"
        }`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"
        />
      </svg>
    </button>
  );
}
