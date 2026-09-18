import { formatDate, formatDateTime } from "@/lib/format";

/**
 * Buyer-branded header.
 *
 * Suppliers decide in the first two seconds whether a link is genuine, so this
 * leads with the buyer's company name (not our product name): the thing the
 * supplier recognises is who is asking for the price. The RFQ summary sits
 * directly underneath so nothing has to be scrolled to before typing begins.
 */
export default function BrandedHeader({ preview }) {
  const company = preview?.buyer_company || "the buyer";
  const initial = String(company).trim().charAt(0).toUpperCase() || "B";
  const deadline = preview?.deadline ? formatDateTime(preview.deadline) : "";

  return (
    <header className="border-b border-border-default bg-surface">
      <div className="mx-auto w-full max-w-2xl px-4">
        <div className="flex items-center justify-between gap-3 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <span
              aria-hidden="true"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-base font-bold text-primary-fg"
            >
              {initial}
            </span>
            <div className="min-w-0">
              <p className="truncate text-base font-semibold leading-5 text-content">
                {company}
              </p>
              <p className="text-xs text-muted">Request for quotation</p>
            </div>
          </div>
          <span className="hidden shrink-0 items-center gap-1.5 rounded-full border border-border-default px-3 py-1 text-xs font-medium text-muted sm:flex">
            <span aria-hidden="true">&#128274;</span>
            Secure quote link
          </span>
        </div>

        <div className="rounded-b-none pb-4">
          <h1 className="text-xl font-bold leading-7 text-content sm:text-2xl">
            {preview?.item_name || "Quote request"}
          </h1>
          {preview?.specification ? (
            <p className="mt-1 text-sm leading-5 text-muted">
              {preview.specification}
            </p>
          ) : null}

          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
            <div className="min-w-0">
              <dt className="text-xs uppercase tracking-wide text-subtle">
                RFQ
              </dt>
              <dd className="truncate font-semibold text-content">
                {preview?.rfq_number || "—"}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs uppercase tracking-wide text-subtle">
                Quantity
              </dt>
              <dd className="truncate font-semibold text-content">
                {preview?.quantity != null
                  ? `${preview.quantity} ${preview.unit || ""}`.trim()
                  : "—"}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs uppercase tracking-wide text-subtle">
                Wanted by
              </dt>
              <dd className="truncate font-semibold text-content">
                {preview?.delivery_expectation
                  ? formatDate(preview.delivery_expectation)
                  : "—"}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs uppercase tracking-wide text-subtle">
                Incoterms
              </dt>
              <dd className="truncate font-semibold text-content">
                {preview?.incoterms || "—"}
              </dd>
            </div>
          </dl>

          {deadline ? (
            <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-warning-soft px-3 py-1.5 text-xs font-semibold text-warning-soft-fg">
              <span aria-hidden="true">&#9200;</span>
              Please reply by {deadline}
            </p>
          ) : null}
        </div>
      </div>
    </header>
  );
}
