import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { toast } from "sonner";

import ConfirmModal from "@/shared/components/ConfirmModal";
import EmptyState from "@/shared/components/EmptyState";
import { SkeletonCard } from "@/shared/components/Loading";
import { Button } from "@/shared/components/ui";
import { buttonClass } from "@/shared/lib/button";
import { formatNumber } from "@/shared/lib/format";
import { RFQ_STATUS_OPTIONS } from "@/shared/lib/status";

import { deleteRFQ } from "../api";
import { useRFQs } from "../hooks";
import RFQCard from "../components/RFQCard";

/**
 * The RFQ register: every request with its response progress, deadline
 * countdown and status. Creating an RFQ lives on its own page (`/rfqs/new`)
 * because the form now includes a suppliers step that does not belong in a
 * modal.
 */
function RFQListPage() {
  const { rfqs, loading, refresh } = useRFQs();

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedRFQ, setSelectedRFQ] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const visibleRFQs = useMemo(() => {
    const term = query.trim().toLowerCase();

    return rfqs.filter((rfq) => {
      if (statusFilter !== "all" && rfq.status !== statusFilter) return false;

      if (!term) return true;

      return [rfq.item_name, rfq.rfq_number, rfq.specification, rfq.category, rfq.site_name]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(term));
    });
  }, [rfqs, query, statusFilter]);

  const handleDeleteRFQ = (rfq) => {
    setSelectedRFQ(rfq);
    setShowDeleteModal(true);
  };

  const confirmDeleteRFQ = async () => {
    if (!selectedRFQ) return;

    try {
      setIsDeleting(true);

      await deleteRFQ(selectedRFQ.id);

      toast.success("RFQ deleted successfully.");

      setShowDeleteModal(false);
      setSelectedRFQ(null);

      await refresh();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-content sm:text-3xl">
              Request for Quotations
            </h1>
            {rfqs.length > 0 && (
              <span className="rounded-full bg-surface-2 px-2.5 py-0.5 text-sm font-semibold text-muted">
                {formatNumber(rfqs.length)}
              </span>
            )}
          </div>

          <p className="mt-2 text-muted">
            Raise a request for maintenance or minor works (or goods), invite
            suppliers, track who has responded, and compare the rates you get back.
          </p>
        </div>

        <Link to="/rfqs/new" className={buttonClass("primary", "md")}>
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
          </svg>
          Create RFQ
        </Link>
      </div>

      {rfqs.length > 0 && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-xs">
            <svg
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z"
              />
            </svg>

            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search scope, RFQ number, category, site…"
              aria-label="Search RFQs"
              className="w-full rounded-xl border border-border-default bg-surface py-2.5 pl-9 pr-3 text-sm text-content placeholder:text-subtle transition focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/50"
            />
          </div>

          <div className="flex flex-wrap gap-1.5">
            {[{ value: "all", label: "All" }, ...RFQ_STATUS_OPTIONS].map(
              (option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setStatusFilter(option.value)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                    statusFilter === option.value
                      ? "bg-primary-soft text-primary-soft-fg"
                      : "bg-surface-2 text-muted hover:text-content"
                  }`}
                >
                  {option.label}
                </button>
              )
            )}
          </div>
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:gap-5">
          {Array.from({ length: 3 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      ) : rfqs.length === 0 ? (
        <EmptyState
          title="No RFQs yet"
          description="Raise your first request, add the contractors you want rates from, and each one gets a private form link."
          action={
            <Link to="/rfqs/new" className={buttonClass("primary", "md")}>
              Create your first RFQ
            </Link>
          }
        />
      ) : visibleRFQs.length === 0 ? (
        <EmptyState
          title="No RFQ matches those filters"
          description="Try a different search term or clear the status filter."
          action={
            <Button
              variant="outline"
              onClick={() => {
                setQuery("");
                setStatusFilter("all");
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:gap-5">
          {visibleRFQs.map((rfq) => (
            <RFQCard key={rfq.id} rfq={rfq} onDelete={handleDeleteRFQ} />
          ))}
        </div>
      )}

      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false);
          setSelectedRFQ(null);
        }}
        onConfirm={confirmDeleteRFQ}
        title="Delete RFQ"
        description={`Are you sure you want to delete "${selectedRFQ?.item_name}"? This also removes its supplier invitations, quotes and follow-ups.`}
        confirmText="Delete"
        isLoading={isDeleting}
      />
    </div>
  );
}

export default RFQListPage;
