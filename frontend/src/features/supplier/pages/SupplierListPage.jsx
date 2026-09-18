/*
 * Supplier directory slice.
 *
 * Owns the buyer's vendor records end to end: the directory table, the create
 * and edit modal (both wrapping SupplierForm), the delete confirmation, plus
 * the search and roll-up summary above the table.
 *
 * Layout of the slice:
 *   api.js    – the five `/suppliers` endpoints
 *   hooks.js  – list fetch + error handling (useSuppliers) and the pure
 *               counter roll-up (summariseSuppliers)
 *   components/SupplierForm.jsx – the field-level contract of a supplier
 *
 * Every number in the table comes from the `SupplierStats` payload of
 * `GET /suppliers` and is parsed with `toNumber()` first, because the backend
 * serialises counts and `average_response_hours` as JSON strings.
 */

import { useMemo, useState } from "react";

import { toast } from "sonner";

import ConfirmModal from "@/shared/components/ConfirmModal";
import EmptyState from "@/shared/components/EmptyState";
import { SkeletonCard } from "@/shared/components/Loading";
import Modal from "@/shared/components/Modal";
import { Button, inputClass } from "@/shared/components/ui";
import { formatNumber, toNumber } from "@/shared/lib/format";
import { RiskBadge } from "@/shared/components/StatusBadge";

import { createSupplier, deleteSupplier, getSupplierById, updateSupplier } from "../api";
import { summariseSuppliers, useSuppliers } from "../hooks";
import SupplierForm from "../components/SupplierForm";

const COLUMN_COUNT = 10;

/** `responded / invited` as a whole percentage; an em dash with no invitations. */
function formatResponseRate(responded, invitations) {
  const invited = toNumber(invitations);

  if (invited === null || invited <= 0) {
    return "—";
  }

  const responses = toNumber(responded) ?? 0;

  return `${Math.round((responses / invited) * 100)}%`;
}

/** `18.5` -> "18.5 h"; `null` -> "—". */
function formatAverageResponse(hours) {
  const value = toNumber(hours);

  if (value === null) {
    return "—";
  }

  return `${formatNumber(value, { maximumFractionDigits: 1 })} h`;
}

function Th({ children, align = "left" }) {
  return (
    <th
      scope="col"
      className={`whitespace-nowrap px-5 py-3 text-xs font-semibold uppercase tracking-wide text-subtle ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

function SupplierListPage() {
  const { suppliers, loading, error, refresh } = useSuppliers();

  const [search, setSearch] = useState("");

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [loadingSupplierId, setLoadingSupplierId] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const summary = useMemo(() => summariseSuppliers(suppliers), [suppliers]);

  const query = search.trim().toLowerCase();

  const visibleSuppliers = useMemo(() => {
    if (!query) return suppliers;

    return suppliers.filter((supplier) =>
      [supplier.name, supplier.contact_name, supplier.contact_email, supplier.country]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query))
    );
  }, [suppliers, query]);

  const handleCreateSupplier = async (payload) => {
    try {
      setIsSubmitting(true);

      await createSupplier(payload);

      setShowCreateModal(false);

      toast.success("Supplier added.");

      await refresh();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Open the edit modal with the *server's* copy of the supplier. The directory
   * row already holds every field, but re-reading the record keeps the form
   * honest if another screen changed it a moment ago.
   */
  const handleEditSupplier = async (supplier) => {
    try {
      setLoadingSupplierId(supplier.id);

      const detail = await getSupplierById(supplier.id);

      setEditingSupplier(detail);
      setShowEditModal(true);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setLoadingSupplierId(null);
    }
  };

  const handleUpdateSupplier = async (payload) => {
    if (!editingSupplier) {
      return;
    }

    try {
      setIsSubmitting(true);

      await updateSupplier(editingSupplier.id, payload);

      setShowEditModal(false);
      setEditingSupplier(null);

      toast.success("Supplier updated.");

      await refresh();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteSupplier = (supplier) => {
    setSelectedSupplier(supplier);
    setShowDeleteModal(true);
  };

  const confirmDeleteSupplier = async () => {
    if (!selectedSupplier) {
      return;
    }

    try {
      setIsDeleting(true);

      await deleteSupplier(selectedSupplier.id);

      toast.success("Supplier deleted.");

      setShowDeleteModal(false);
      setSelectedSupplier(null);

      await refresh();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const hasSuppliers = suppliers.length > 0;
  const showInitialLoading = loading && !hasSuppliers;

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-content sm:text-3xl">
              Suppliers
            </h1>
            {hasSuppliers && (
              <span className="rounded-full bg-surface-2 px-2.5 py-0.5 text-sm font-semibold text-muted">
                {suppliers.length}
              </span>
            )}
          </div>

          <p className="mt-2 text-muted">
            Your vendor directory — contacts, coverage and how reliably each
            supplier responds.
          </p>
        </div>

        <Button onClick={() => setShowCreateModal(true)}>
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
          </svg>
          Add supplier
        </Button>
      </div>

      {error && (
        <div className="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger-soft-fg sm:flex-row sm:items-center sm:justify-between">
          <p className="leading-relaxed">{error}</p>
          <Button variant="outline" size="sm" onClick={refresh}>
            Try again
          </Button>
        </div>
      )}

      {showInitialLoading ? (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : !hasSuppliers ? (
        error ? null : (
          <EmptyState
            title="No suppliers yet"
            description="Add the vendors you buy from so you can invite them to RFQs and track how they respond."
            action={
              <Button onClick={() => setShowCreateModal(true)}>
                Add your first supplier
              </Button>
            }
          />
        )
      ) : (
        <div className="space-y-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by name, contact, email or country…"
              aria-label="Search suppliers"
              className={`${inputClass} sm:max-w-sm`}
            />

            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full bg-surface-2 px-3 py-1 font-medium text-muted">
                {formatNumber(summary.total)} suppliers
              </span>
              <span className="rounded-full bg-surface-2 px-3 py-1 font-medium text-muted">
                {formatNumber(summary.invited)} invitations sent
              </span>
              <span className="rounded-full bg-primary-soft px-3 py-1 font-medium text-primary-soft-fg">
                {formatNumber(summary.responded)} responses
              </span>
              <span className="rounded-full bg-success-soft px-3 py-1 font-medium text-success-soft-fg">
                {formatNumber(summary.quotesReceived)} quotes received
              </span>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-border-default bg-surface-2">
                    <Th>Name</Th>
                    <Th>Contact</Th>
                    <Th>Email</Th>
                    <Th>Country</Th>
                    <Th>Risk</Th>
                    <Th align="right">Invitations sent</Th>
                    <Th align="right">Response rate</Th>
                    <Th align="right">Quotes received</Th>
                    <Th align="right">Avg response</Th>
                    <Th align="right">Actions</Th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-border-default">
                  {visibleSuppliers.length === 0 ? (
                    <tr>
                      <td
                        colSpan={COLUMN_COUNT}
                        className="px-5 py-12 text-center text-sm text-muted"
                      >
                        No suppliers match “{search.trim()}”.
                      </td>
                    </tr>
                  ) : (
                    visibleSuppliers.map((supplier) => (
                      <tr
                        key={supplier.id}
                        className="transition hover:bg-surface-2"
                      >
                        <td className="px-5 py-4 align-top">
                          <div className="font-medium text-content">
                            {supplier.name}
                          </div>
                          {supplier.external_ref && (
                            <div className="mt-0.5 text-xs text-subtle">
                              {supplier.external_ref}
                            </div>
                          )}
                        </td>

                        <td className="px-5 py-4 align-top">
                          <div className="text-content">
                            {supplier.contact_name || "—"}
                          </div>
                          <div className="mt-0.5 text-xs text-subtle">
                            {supplier.contact_email}
                          </div>
                        </td>

                        <td className="px-5 py-4 align-top">
                          <a
                            href={`mailto:${supplier.contact_email}`}
                            className="text-content underline-offset-2 hover:text-primary-soft-fg hover:underline"
                          >
                            {supplier.contact_email}
                          </a>
                        </td>

                        <td className="px-5 py-4 align-top">
                          <div className="text-content">
                            {supplier.country || "—"}
                          </div>
                          {supplier.city && (
                            <div className="mt-0.5 text-xs text-subtle">
                              {supplier.city}
                            </div>
                          )}
                        </td>

                        <td className="px-5 py-4 align-top">
                          <RiskBadge rating={supplier.risk_rating} />
                        </td>

                        <td className="px-5 py-4 text-right align-top text-muted">
                          {formatNumber(supplier.invitations_total)}
                        </td>

                        <td className="px-5 py-4 text-right align-top text-muted">
                          {formatResponseRate(
                            supplier.invitations_responded,
                            supplier.invitations_total
                          )}
                        </td>

                        <td className="px-5 py-4 text-right align-top text-muted">
                          {formatNumber(supplier.quotes_total)}
                        </td>

                        <td className="px-5 py-4 text-right align-top text-muted">
                          {formatAverageResponse(supplier.average_response_hours)}
                        </td>

                        <td className="px-5 py-4 align-top">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="soft"
                              size="sm"
                              onClick={() => handleEditSupplier(supplier)}
                              loading={loadingSupplierId === supplier.id}
                              loadingText="Loading…"
                            >
                              Edit
                            </Button>

                            <button
                              type="button"
                              onClick={() => handleDeleteSupplier(supplier)}
                              aria-label={`Delete ${supplier.name}`}
                              className="inline-flex items-center justify-center rounded-lg bg-surface-2 px-3 py-2 text-subtle transition hover:bg-danger-soft hover:text-danger-soft-fg"
                            >
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
                                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                />
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Add supplier"
        description="Suppliers in your directory can be invited to future RFQs."
      >
        <SupplierForm
          onSubmit={handleCreateSupplier}
          onCancel={() => setShowCreateModal(false)}
          submitLabel="Add supplier"
          isSubmitting={isSubmitting}
        />
      </Modal>

      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditingSupplier(null);
        }}
        title="Edit supplier"
        description={editingSupplier?.name}
      >
        <SupplierForm
          initialValues={editingSupplier ?? {}}
          onSubmit={handleUpdateSupplier}
          onCancel={() => {
            setShowEditModal(false);
            setEditingSupplier(null);
          }}
          submitLabel="Save changes"
          isSubmitting={isSubmitting}
        />
      </Modal>

      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false);
          setSelectedSupplier(null);
        }}
        onConfirm={confirmDeleteSupplier}
        title="Delete supplier"
        description={`Are you sure you want to delete "${selectedSupplier?.name}"? This permanently removes the supplier from your directory.`}
        confirmText="Delete"
        isLoading={isDeleting}
      />
    </div>
  );
}

export default SupplierListPage;
