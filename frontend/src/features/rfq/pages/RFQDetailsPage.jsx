import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { toast } from "sonner";

import Modal from "@/shared/components/Modal";
import ConfirmModal from "@/shared/components/ConfirmModal";
import Loading from "@/shared/components/Loading";
import { Badge, Button } from "@/shared/components/ui";
import { formatDate } from "@/shared/lib/format";

import {
  createQuote,
  deleteQuote,
  importQuotes,
  updateQuote,
} from "@/features/quote/api";
import { useQuotes } from "@/features/quote/hooks";
import QuoteForm from "@/features/quote/components/QuoteForm";
import QuoteTable from "@/features/quote/components/QuoteTable";
import FileImport from "@/features/quote/components/FileImport";

import { useRFQ } from "../hooks";

function RFQDetailsPage() {
  const { id } = useParams();

  const { rfq, loading: rfqLoading } = useRFQ(id);
  const { quotes, loading: quotesLoading, refresh: refreshQuotes } =
    useQuotes(id);

  const [showQuoteForm, setShowQuoteForm] = useState(false);
  const [editingQuote, setEditingQuote] = useState(null);
  const [savingQuote, setSavingQuote] = useState(false);

  const [uploadingCsv, setUploadingCsv] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedQuote, setSelectedQuote] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleSaveQuote = async (payload) => {
    try {
      setSavingQuote(true);

      if (editingQuote) {
        await updateQuote(editingQuote.id, payload);
        toast.success("Supplier quote updated successfully.");
      } else {
        await createQuote(id, payload);
        toast.success("Supplier quote added successfully.");
      }

      await refreshQuotes();

      setEditingQuote(null);
      setShowQuoteForm(false);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSavingQuote(false);
    }
  };

  const handleEditQuote = (quote) => {
    setEditingQuote(quote);
    setShowQuoteForm(true);
  };

  const handleDeleteQuote = (quote) => {
    setSelectedQuote(quote);
    setShowDeleteModal(true);
  };

  const confirmDeleteQuote = async () => {
    if (!selectedQuote) {
      return;
    }

    try {
      setIsDeleting(true);

      await deleteQuote(selectedQuote.id);

      toast.success("Supplier quote deleted successfully.");

      setShowDeleteModal(false);
      setSelectedQuote(null);

      await refreshQuotes();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCsvUpload = async (file) => {
    try {
      setUploadingCsv(true);

      const result = await importQuotes(id, file);

      await refreshQuotes();

      toast.success(`Imported ${result.imported} quotes successfully.`);

      if (result.failed > 0) {
        toast.warning(`${result.failed} rows could not be imported.`);
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setUploadingCsv(false);
    }
  };

  if (rfqLoading || quotesLoading) {
    return <Loading message="Loading RFQ..." />;
  }

  if (!rfq) {
    return null;
  }

  const formattedDelivery = formatDate(rfq.delivery_expectation);

  return (
    <div className="space-y-8">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-muted transition hover:text-content"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back to RFQs
      </Link>

      <section className="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card">
        <div className="border-b border-border-default bg-surface-2/50 px-6 py-5">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-2xl font-bold tracking-tight text-content">
                  {rfq.item_name}
                </h1>
                {rfq.specification && (
                  <Badge variant="primary">{rfq.specification}</Badge>
                )}
              </div>
              <p className="text-sm text-muted">
                Compare supplier quotes for this request below.
              </p>
            </div>

            <Button
              className="shrink-0"
              onClick={() => {
                setEditingQuote(null);
                setShowQuoteForm(true);
              }}
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 5v14m-7-7h14"
                />
              </svg>
              Add Quote
            </Button>
          </div>
        </div>

        <dl className="grid grid-cols-2 divide-x divide-y divide-border-default sm:grid-cols-4 sm:divide-y-0">
          <DetailItem label="Quantity" value={rfq.quantity?.toLocaleString()} />
          <DetailItem label="Delivery" value={formattedDelivery} />
          <DetailItem label="Specification" value={rfq.specification || "—"} />
          <DetailItem label="Notes" value={rfq.notes || "—"} />
        </dl>
      </section>

      <FileImport onUpload={handleCsvUpload} isUploading={uploadingCsv} />

      <Modal
        isOpen={showQuoteForm}
        onClose={() => {
          setShowQuoteForm(false);
          setEditingQuote(null);
        }}
        title={editingQuote ? "Edit Supplier Quote" : "Add Supplier Quote"}
      >
        <QuoteForm
          initialValues={editingQuote || {}}
          onSubmit={handleSaveQuote}
          onCancel={() => {
            setShowQuoteForm(false);
            setEditingQuote(null);
          }}
          submitLabel={editingQuote ? "Update Quote" : "Add Quote"}
          isSubmitting={savingQuote}
        />
      </Modal>

      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false);
          setSelectedQuote(null);
        }}
        onConfirm={confirmDeleteQuote}
        title="Delete Supplier Quote"
        description={`Are you sure you want to delete the quote from "${selectedQuote?.supplier_name}"?`}
        confirmText="Delete"
        isLoading={isDeleting}
      />

      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-content">
              Supplier Quotes
            </h2>

            <p className="mt-1 text-sm text-muted">
              {quotes.length > 0
                ? "The lowest total price is highlighted."
                : "No supplier quotes available yet."}
            </p>
          </div>

          {quotes.length > 0 && (
            <span className="rounded-full bg-surface-2 px-2.5 py-0.5 text-sm font-semibold text-muted">
              {quotes.length}
            </span>
          )}
        </div>

        <QuoteTable
          quotes={quotes}
          onEdit={handleEditQuote}
          onDelete={handleDeleteQuote}
        />
      </section>
    </div>
  );
}

function DetailItem({ label, value }) {
  return (
    <div className="px-6 py-4">
      <dt className="text-xs font-medium uppercase tracking-wider text-subtle">
        {label}
      </dt>
      <dd className="mt-1 truncate text-sm font-medium text-content">{value}</dd>
    </div>
  );
}

export default RFQDetailsPage;
