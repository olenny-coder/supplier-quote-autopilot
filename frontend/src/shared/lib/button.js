/**
 * Button styling, shared with links.
 *
 * `Button` (in `shared/components/ui`) renders a real `<button>`. Sometimes the
 * same look has to be a router `<Link>` instead — never nest a button inside an
 * anchor, which is invalid HTML and a screen-reader trap. This module owns the
 * class strings so both paths stay identical, and it lives in `lib/` rather than
 * beside the components so the UI kit keeps exporting components only (which is
 * what React Fast Refresh needs).
 *
 * `sm` and `md` are the dense desktop sizes. `lg` exists for anything a thumb is
 * expected to hit on a phone: 44px is the minimum touch target both Apple and
 * Google publish, and `sm` is 36px — fine with a mouse, a coin-toss with a thumb.
 */

const buttonBase =
  "inline-flex items-center justify-center gap-2 rounded-xl text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-60";

const buttonSizes = {
  sm: "px-3.5 py-2",
  md: "px-5 py-2.5",
  lg: "min-h-11 px-5 py-2.5",
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

/**
 * `buttonClass("outline", "sm")` -> the class string for that button look.
 * Usable as `<Link className={buttonClass("soft", "sm")}>…</Link>`.
 */
export function buttonClass(variant = "primary", size = "md") {
  return `${buttonBase} ${buttonSizes[size]} ${buttonVariants[variant]}`;
}
