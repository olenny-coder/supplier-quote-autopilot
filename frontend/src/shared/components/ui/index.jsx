/*
 * Shared UI primitives. Centralizing tokens here keeps the visual language
 * consistent and makes future restyling a single-file change.
 */

import { buttonClass } from "@/shared/lib/button";

export const inputClass =
  "w-full rounded-xl border border-border-default bg-surface-inset px-4 py-2.5 text-sm text-content placeholder:text-subtle transition focus:border-primary focus:bg-surface focus:outline-none focus:ring-2 focus:ring-ring/50";

export function FormField({ label, hint, required, error, children }) {
  return (
    <div>
      {label && (
        <label className="mb-1.5 block text-sm font-medium text-content">
          {label}
          {required && <span className="ml-0.5 text-danger">*</span>}
          {hint && (
            <span className="ml-2 text-xs font-normal text-subtle">{hint}</span>
          )}
        </label>
      )}
      {children}
      {error && <p className="mt-1.5 text-xs text-danger">{error}</p>}
    </div>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  loadingText,
  className = "",
  children,
  disabled,
  ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      // The look itself lives in `shared/lib/button` so a `<Link>` can wear it
      // too, without this file exporting a non-component (Fast Refresh).
      className={`${buttonClass(variant, size)} ${className}`}
      {...props}
    >
      {loading && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current/30 border-t-current" />
      )}
      {loading ? loadingText || children : children}
    </button>
  );
}

export function Card({ className = "", children, ...props }) {
  return (
    <div
      className={`rounded-2xl border border-border-default bg-surface shadow-card ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function Badge({ variant = "neutral", className = "", children }) {
  const variants = {
    neutral: "bg-surface-2 text-muted",
    primary: "bg-primary-soft text-primary-soft-fg",
    success: "bg-success-soft text-success-soft-fg",
    danger: "bg-danger-soft text-danger-soft-fg",
    warning: "bg-warning-soft text-warning-soft-fg",
  };

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${variants[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
