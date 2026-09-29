import { useMemo, useState } from "react";

import { toast } from "sonner";

import EmptyState from "@/shared/components/EmptyState";
import Loading from "@/shared/components/Loading";
import { Badge, Button, Select } from "@/shared/components/ui";
import { formatDateTime } from "@/shared/lib/format";

import { downloadAuditCsv } from "../api";
import { useAuditLog } from "../hooks";

/**
 * The workspace audit log.
 *
 * What this page is for: answering "what happened here?" without reading six
 * screens. A buyer uses it to reconstruct a tender — when the RFQ went out, when
 * each supplier actually answered, who was chased and how often, what the engine
 * recommended, and who approved the award and why — and to hand that to somebody
 * who was not involved. The CSV is the same list, filtered the same way, for
 * filing.
 *
 * The filters are deliberately few. Action, actor type and RFQ cover the three
 * questions people actually ask ("what did the system do?", "what did suppliers
 * do?", "what happened on this job?"); a free-text search box was left out because
 * the log is short enough to read and a search that silently misses a row is worse
 * than no search.
 */

const ACTOR_LABELS = {
  buyer: "You and your team",
  supplier: "Suppliers",
  system: "Automatic (scheduler)",
};

//: Tone per actor, so the origin of a line is visible before it is read.
const ACTOR_TONES = {
  buyer: "primary",
  supplier: "success",
  system: "neutral",
};

const ENTITY_LABELS = {
  rfq: "RFQ",
  supplier: "Supplier",
  invitation: "Invitation",
  quote: "Quote",
  comparison: "Comparison",
  approval: "Award",
  followup: "Follow-up",
  user: "Account",
};

/** Rows per request. Also the size of the "Load more" step. */
const PAGE_SIZE = 50;

function DetailCell({ detail }) {
  const [open, setOpen] = useState(false);

  if (!detail || Object.keys(detail).length === 0) {
    return <span className="text-subtle">—</span>;
  }

  // First key shown inline; the rest behind a toggle. Most entries have one or two
  // keys, and a table full of expanded JSON is unreadable.
  const entries = Object.entries(detail);

  return (
    <div className="text-xs text-muted">
      <button
        type="button"
        onClick={() => setOpen((previous) => !previous)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 rounded font-medium text-primary transition hover:underline"
      >
        {open ? "Hide detail" : `Detail (${entries.length})`}
      </button>

      {open && (
        <dl className="mt-2 space-y-1 border-l-2 border-border-default pl-3">
          {entries.map(([key, value]) => (
            <div key={key} className="flex flex-wrap gap-x-1.5">
              <dt className="font-medium text-content">{key}</dt>
              <dd className="break-all">
                {value === null || value === undefined || value === ""
                  ? "—"
                  : typeof value === "object"
                    ? JSON.stringify(value)
                    : String(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

function AuditLogPage() {
  const [action, setAction] = useState("");
  const [actorType, setActorType] = useState("");
  const [entityType, setEntityType] = useState("");
  const [rfqId, setRfqId] = useState("");
  const [downloading, setDownloading] = useState(false);

  // Rebuilt each render but compared by value inside the hook, so the log is not
  // refetched unless something actually changed.
  const filters = useMemo(
    () => ({ action, actor_type: actorType, entity_type: entityType, rfq_id: rfqId }),
    [action, actorType, entityType, rfqId]
  );

  const {
    entries,
    total,
    availableActions,
    availableRfqs,
    loading,
    loadingMore,
    error,
    hasMore,
    loadMore,
    refresh,
  } = useAuditLog(filters, PAGE_SIZE);

  const filtered = Boolean(action || actorType || entityType || rfqId);

  const handleDownload = async () => {
    try {
      setDownloading(true);

      await downloadAuditCsv(filters);

      // Downloading is not a change to the workspace, so it is not written to the
      // log — but the buyer should still know it worked, because a blocked
      // download fails silently otherwise.
      toast.success("Audit log downloaded.");
    } catch (failure) {
      toast.error(failure.message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-content sm:text-3xl">
            Audit log
          </h1>
          <p className="mt-2 max-w-2xl text-muted">
            Everything that has happened in this workspace, newest first — who
            created, changed, emailed or decided what, including the messages the
            scheduler sent on your behalf. Entries are written as the action
            happens and can never be edited or removed.
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" size="sm" loading={loading} onClick={refresh}>
            Refresh
          </Button>

          <Button size="sm" loading={downloading} onClick={handleDownload}>
            {!downloading && (
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12m0 0l-4-4m4 4l4-4"
                />
              </svg>
            )}
            Download CSV
          </Button>
        </div>
      </div>

      <div className="grid gap-3 rounded-2xl border border-border-default bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-sm">
          <span className="mb-1.5 block font-medium text-content">Action</span>
          <Select
            value={action}
            onChange={(event) => setAction(event.target.value)}
            allowEmpty
            emptyLabel="All actions"
            options={availableActions.map((option) => ({
              value: option.action,
              label: `${option.label} (${option.count})`,
            }))}
          />
        </label>

        <label className="text-sm">
          <span className="mb-1.5 block font-medium text-content">Who acted</span>
          <Select
            value={actorType}
            onChange={(event) => setActorType(event.target.value)}
            allowEmpty
            emptyLabel="Anyone"
            options={Object.entries(ACTOR_LABELS).map(([value, label]) => ({
              value,
              label,
            }))}
          />
        </label>

        <label className="text-sm">
          <span className="mb-1.5 block font-medium text-content">About</span>
          <Select
            value={entityType}
            onChange={(event) => setEntityType(event.target.value)}
            allowEmpty
            emptyLabel="Anything"
            options={Object.entries(ENTITY_LABELS).map(([value, label]) => ({
              value,
              label,
            }))}
          />
        </label>

        <label className="text-sm">
          <span className="mb-1.5 block font-medium text-content">RFQ</span>
          <Select
            value={rfqId}
            onChange={(event) => setRfqId(event.target.value)}
            allowEmpty
            emptyLabel="Every RFQ"
            options={availableRfqs.map((option) => ({
              value: String(option.rfq_id),
              label: option.rfq_number || `#${option.rfq_id}`,
            }))}
          />
        </label>
      </div>

      <p className="text-sm text-muted">
        {loading
          ? "Loading…"
          : `Showing ${entries.length} of ${total} ${total === 1 ? "entry" : "entries"}${
              filtered ? " matching these filters" : ""
            }.`}
      </p>

      {error && !loading && (
        <div className="rounded-2xl border border-danger/30 bg-danger-soft px-5 py-4 text-sm text-danger-soft-fg">
          {error}
        </div>
      )}

      {loading && entries.length === 0 ? (
        <Loading message="Loading the audit log…" />
      ) : entries.length === 0 ? (
        <EmptyState
          title={filtered ? "Nothing matches those filters" : "Nothing logged yet"}
          description={
            filtered
              ? "Try widening the filters — the log only holds what this workspace has actually done."
              : "As soon as you create an RFQ, invite a supplier or record a decision, it appears here."
          }
        />
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border-default bg-surface-2 text-xs uppercase tracking-wide text-subtle">
                <tr>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold">When</th>
                  <th className="px-4 py-3 font-semibold">What happened</th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold">Who</th>
                  <th className="whitespace-nowrap px-4 py-3 font-semibold">RFQ</th>
                  <th className="px-4 py-3 font-semibold">Detail</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border-default">
                {entries.map((entry) => (
                  <tr key={entry.id} className="align-top hover:bg-surface-hover">
                    <td className="whitespace-nowrap px-4 py-3 text-muted">
                      {formatDateTime(entry.created_at)}
                    </td>

                    <td className="px-4 py-3">
                      <p className="font-medium text-content">{entry.action_label}</p>
                      <p className="mt-0.5 text-muted">{entry.summary}</p>
                    </td>

                    <td className="whitespace-nowrap px-4 py-3">
                      <Badge variant={ACTOR_TONES[entry.actor_type] || "neutral"}>
                        {entry.actor_type === "supplier"
                          ? entry.actor_label
                          : entry.actor_type === "system"
                            ? "Scheduler"
                            : "You"}
                      </Badge>
                      <p className="mt-1 max-w-[12rem] truncate text-xs text-subtle">
                        {entry.actor_label}
                      </p>
                    </td>

                    <td className="whitespace-nowrap px-4 py-3 text-muted">
                      {entry.rfq_number ? (
                        <span className="font-mono text-xs">{entry.rfq_number}</span>
                      ) : (
                        <span className="text-subtle">—</span>
                      )}
                    </td>

                    <td className="px-4 py-3">
                      <DetailCell detail={entry.detail} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <div className="border-t border-border-default p-4 text-center">
              <Button
                variant="outline"
                size="sm"
                loading={loadingMore}
                onClick={loadMore}
              >
                Load {Math.min(PAGE_SIZE, total - entries.length)} more
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AuditLogPage;
