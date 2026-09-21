import { Link } from "react-router-dom";

import { buttonClass } from "@/shared/lib/button";

/**
 * The bar that follows a visitor around the demo.
 *
 * Sticky rather than a one-off notice at the top of the page: the sample data is
 * indistinguishable from a real workspace at a glance, and a visitor who scrolls
 * to the comparison table and then starts reading a supplier name has to be able
 * to see, without scrolling back, that nothing here is theirs and nothing here is
 * saved. It is deliberately the only sticky element on the page so it is never
 * covered by a header.
 *
 * The sign-up link lives here as well as in the page hero: this is the element a
 * visitor is looking at when the question "so how do I do this with my own RFQ?"
 * occurs to them.
 */
function DemoBanner() {
  return (
    <div className="sticky top-0 z-30 border-b border-border-default bg-warning-soft backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6">
        <div className="flex items-start gap-2.5">
          <svg
            className="mt-0.5 h-4 w-4 shrink-0 text-warning-soft-fg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m0 3.75h.008M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
            />
          </svg>

          <p className="text-xs leading-relaxed text-warning-soft-fg sm:text-sm">
            <span className="font-semibold">
              You are viewing a read-only demo.
            </span>{" "}
            Nothing here is saved and no email is ever sent — every button that
            would change something is turned off.
          </p>
        </div>

        <Link
          to="/register"
          className={`${buttonClass("primary", "lg")} shrink-0`}
        >
          Create your workspace
        </Link>
      </div>
    </div>
  );
}

export default DemoBanner;
