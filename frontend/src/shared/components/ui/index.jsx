/*
 * Shared UI primitives. Centralizing tokens here keeps the visual language
 * consistent and makes future restyling a single-file change.
 */

import { buttonClass } from "@/shared/lib/button";

/**
 * The one input style, at 16px on phones.
 *
 * iOS Safari zooms the whole viewport when a focused control's font-size is below
 * 16px, and it does not zoom back out afterwards — so at `text-sm` every field in
 * this app cost the buyer a pinch-to-zoom, on a page whose sticky header then
 * covered the field they had just tapped. 16px on small screens avoids it, and
 * `sm:text-sm` keeps the denser look on a desktop where nothing zooms.
 */
export const inputClass =
  "w-full rounded-xl border border-border-default bg-surface-inset px-4 py-2.5 text-base text-content placeholder:text-subtle transition focus:border-primary focus:bg-surface focus:outline-none focus:ring-2 focus:ring-ring/50 sm:text-sm";

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

/**
 * Select over a list that came from the API.
 *
 * `options` accepts plain strings (`meta.service_categories`,
 * `meta.service_rate_bases`) or `{ value, label }` pairs. When the list is empty
 * — the taxonomy request failed, or has not landed yet — it degrades to a
 * free-text input rather than rendering a picker with nothing in it: a buyer
 * typing a category is a better outcome than a form they cannot submit, and it
 * keeps this component free of any hard-coded category list.
 */
export function Select({
  options = [],
  placeholder = "",
  allowEmpty = false,
  emptyLabel = "Not specified",
  className = "",
  ...props
}) {
  const classes = `${inputClass} ${className}`;

  if (!options.length) {
    return (
      <input type="text" placeholder={placeholder} className={classes} {...props} />
    );
  }

  return (
    <select className={classes} {...props}>
      {allowEmpty && <option value="">{emptyLabel}</option>}

      {options.map((option) => {
        const value = typeof option === "string" ? option : option.value;
        const label = typeof option === "string" ? option : option.label;

        return (
          <option key={value} value={value}>
            {label}
          </option>
        );
      })}
    </select>
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
