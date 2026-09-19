import BrandedHeader from "@/components/BrandedHeader";

/**
 * Full-page message view.
 *
 * Used for every dead end a supplier can hit: an invalid token, an expired
 * invitation, a rate limit, a network failure, or a URL that is not a quote link
 * at all. The copy is deliberately non-technical — a supplier who sees "404" or
 * "Failed to fetch" concludes the buyer's system is broken and emails instead.
 *
 * `buyerPreview` is passed when we already hold the invitation (the link expired
 * but the preview was readable), so the supplier still gets a name and a way to
 * reach the buyer instead of a blank wall.
 */
export default function ErrorPage({
  tone = "warning",
  title,
  message,
  buyerPreview = null,
  onRetry,
  retrying = false,
}) {
  const iconTone = tone === "danger" ? "bg-danger-soft text-danger-soft-fg" : "bg-warning-soft text-warning-soft-fg";

  return (
    <div className="flex min-h-screen flex-col">
      {buyerPreview ? <BrandedHeader preview={buyerPreview} /> : null}

      <main className="mx-auto flex w-full max-w-2xl flex-1 items-start justify-center px-4 py-8 sm:py-12">
        <div className="w-full rounded-2xl border border-border-default bg-surface p-5 text-center shadow-card sm:p-7">
          <span
            aria-hidden="true"
            className={`mx-auto flex h-14 w-14 items-center justify-center rounded-full text-2xl font-bold ${iconTone}`}
          >
            {tone === "danger" ? "!" : "?"}
          </span>

          <h1 className="mt-4 text-xl font-bold leading-7 text-content sm:text-2xl">
            {title}
          </h1>
          <p className="mx-auto mt-2 max-w-md text-base leading-6 text-muted">
            {message}
          </p>

          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              disabled={retrying}
              className="mt-5 min-h-[48px] w-full rounded-xl bg-primary px-5 text-base font-semibold text-primary-fg transition-colors hover:bg-primary-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-70 sm:w-auto"
            >
              {retrying ? "Trying again…" : "Try again"}
            </button>
          ) : null}

          {buyerPreview ? (
            <div className="mt-6 rounded-xl bg-surface-2 p-4 text-left">
              <p className="text-sm font-semibold text-content">
                Contact the buyer
              </p>
              <ul className="mt-2 space-y-1.5 text-sm leading-6 text-muted">
                {buyerPreview.buyer_company ? (
                  <li>
                    <span className="text-subtle">Company: </span>
                    {buyerPreview.buyer_company}
                  </li>
                ) : null}
                {buyerPreview.buyer_contact_email ? (
                  <li>
                    <span className="text-subtle">Email: </span>
                    {/* `break-all` because this is the one thing a supplier needs
                        from a dead link, and an address longer than the ~30
                        characters that fit at 320px would otherwise run past the
                        card — clipped, since this app sets `overflow-x: hidden` on
                        the body, so there is no way to scroll to the rest. */}
                    <a
                      className="break-all font-semibold text-primary underline"
                      href={`mailto:${buyerPreview.buyer_contact_email}`}
                    >
                      {buyerPreview.buyer_contact_email}
                    </a>
                  </li>
                ) : null}
                {buyerPreview.buyer_contact_phone ? (
                  <li>
                    <span className="text-subtle">Phone: </span>
                    <a
                      className="break-all font-semibold text-primary underline"
                      href={`tel:${String(buyerPreview.buyer_contact_phone).replace(/\s+/g, "")}`}
                    >
                      {buyerPreview.buyer_contact_phone}
                    </a>
                  </li>
                ) : null}
                {buyerPreview.rfq_number ? (
                  <li>
                    <span className="text-subtle">Quote for: </span>
                    {buyerPreview.item_name || "—"} ({buyerPreview.rfq_number})
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}
        </div>
      </main>

      <footer className="px-4 pb-8 text-center text-xs text-subtle">
        Supplier Quote Autopilot — quotes are sent straight to the buyer.
      </footer>
    </div>
  );
}
