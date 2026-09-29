import { useId } from "react";

/**
 * The product mark: three ascending bars on a rounded indigo tile.
 *
 * **This is the same drawing as the browser icon.** `scripts/make_favicons.py` at
 * the repository root holds the geometry on a 32-unit grid and generates
 * `favicon.svg`, `favicon.ico` and `apple-touch-icon.png` from it; this component
 * renders that drawing as inline SVG so the tab and the page show one mark rather
 * than two. Change the mark in both places, or the logo and the favicon drift —
 * which is exactly what had happened before: the tab carried a checkmark data URI
 * while the header drew a clipboard, and the dashboard's icon 404'd.
 *
 * Inline SVG rather than `<img src="/favicon.svg">` for three reasons: it costs no
 * request, it scales crisply from a 32 px header tile to a 44 px auth panel, and it
 * carries no `<title>`, so each call site keeps control of the accessible name
 * (the mark itself is decorative — the wordmark next to it is the label).
 *
 * The gradient id is per-instance because a page renders this more than once
 * (header and auth panel, or demo page and footer). Duplicate ids are invalid HTML
 * and `url(#id)` would silently bind every copy to the first one in the document.
 * `useId` returns a value containing colons, which are legal in an HTML id but
 * awkward inside a `url(#…)` reference, so they are stripped.
 */
export function LogoMark({ size = 36, className = "" }) {
  const gradientId = `logo-tile-${useId().replace(/:/g, "")}`;

  return (
    <svg
      aria-hidden="true"
      focusable="false"
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
    >
      <defs>
        <linearGradient
          id={gradientId}
          x1="0"
          y1="0"
          x2="32"
          y2="32"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#6a6df5" />
          <stop offset="1" stopColor="#4d50e0" />
        </linearGradient>
      </defs>

      <rect width="32" height="32" rx="7" fill={`url(#${gradientId})`} />

      <g fill="#ffffff">
        <rect x="8" y="17" width="4" height="7" rx="2" />
        <rect x="14" y="13" width="4" height="11" rx="2" />
        <rect x="20" y="9" width="4" height="15" rx="2" />
      </g>
    </svg>
  );
}

/**
 * The mark with the drop shadow the app's brand lockups use.
 *
 * The shadow lives on a wrapper rather than in the SVG: a `box-shadow` on a
 * `border-radius` is cheaper and softer than the SVG equivalent, and the radius is
 * expressed as the same 22% the mark's own corners use (7 of 32 units), so the
 * glow follows the tile instead of ringing a square behind it. `drop-shadow`
 * would trace the bars as well, which muddies them at 32 px.
 */
export function LogoBadge({ size = 36, className = "" }) {
  return (
    <span
      className={`flex shrink-0 rounded-[22%] shadow-lg shadow-primary/25 ${className}`}
    >
      <LogoMark size={size} />
    </span>
  );
}

export default LogoBadge;
