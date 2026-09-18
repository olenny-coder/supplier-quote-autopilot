/*
 * Shared UI primitives. Centralizing tokens here keeps the visual language
 * consistent and makes future restyling a single-file change.
 */

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

const buttonBase =
  "inline-flex items-center justify-center gap-2 rounded-xl text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-60";

const buttonSizes = {
  sm: "px-3.5 py-2",
  md: "px-5 py-2.5",
};

const buttonVariants = {
  primary:
    "bg-primary text-primary-fg shadow-sm shadow-primary/25 hover:bg-primary-hover",
  danger: "bg-danger text-white hover:bg-danger-hover",
  soft: "bg-primary-soft text-primary-soft-fg hover:brightness-105",
  "soft-danger": "bg-danger-soft text-danger-soft-fg hover:brightness-105",
  outline:
    "border border-border-default bg-surface text-content hover:border-border-strong hover:bg-surface-hover",
  ghost: "text-muted hover:bg-surface-2 hover:text-content",
};

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
      className={`${buttonBase} ${buttonSizes[size]} ${buttonVariants[variant]} ${className}`}
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
