import { formatDate } from "@/lib/format";

/**
 * Read-only site and timing context, shown to the contractor as a card.
 *
 * Access hours, permits and the wanted-by date are the details that decide
 * whether a job is worth quoting at all, and they used to be spread across the
 * header and three form groups. Nothing here is editable: these are the buyer's
 * facts, and a supplier who needs them changed must speak to the buyer rather than
 * quietly rewrite the site address on a quote. For the same reason they are
 * rendered as a description list, not disabled inputs — a disabled input looks
 * like something that could be enabled.
 *
 * Renders nothing when the RFQ carries none of this (a goods RFQ, or a services
 * RFQ the buyer left bare), so no empty card appears.
 */
export default function SiteScopeCard({ preview }) {
  const siteName = String(preview?.site_name ?? "").trim();
  const siteAddress = String(preview?.site_address ?? "").trim();
  const accessNotes = String(preview?.site_access_notes ?? "").trim();
  const wantedBy = preview?.delivery_expectation
    ? formatDate(preview.delivery_expectation)
    : "";

  if (!siteName && !siteAddress && !accessNotes && !wantedBy) return null;

  return (
    <section
      aria-labelledby="site-heading"
      className="rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:p-5"
    >
      <h2 id="site-heading" className="text-base font-bold text-content">
        Site and scope
      </h2>
      <p className="mt-1 text-sm text-muted">
        What the buyer told us about the site. These details come from the buyer
        and cannot be changed here — contact them if something looks wrong.
      </p>

      <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
        {siteName ? (
          <div className="min-w-0">
            <dt className="text-xs uppercase tracking-wide text-subtle">Site</dt>
            <dd className="font-semibold text-content">{siteName}</dd>
          </div>
        ) : null}

        {wantedBy ? (
          <div className="min-w-0">
            <dt className="text-xs uppercase tracking-wide text-subtle">
              Works wanted by
            </dt>
            <dd className="font-semibold text-content">{wantedBy}</dd>
          </div>
        ) : null}

        {siteAddress ? (
          <div className="min-w-0 sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-subtle">
              Address
            </dt>
            {/* Pre-line: buyers paste multi-line addresses and directions. */}
            <dd className="whitespace-pre-line text-content">{siteAddress}</dd>
          </div>
        ) : null}

        {accessNotes ? (
          <div className="min-w-0 sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-subtle">
              Access and permits
            </dt>
            <dd className="whitespace-pre-line text-content">{accessNotes}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
