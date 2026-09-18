import { useState } from "react";

import { toast } from "sonner";

import ConfirmModal from "@/shared/components/ConfirmModal";
import Modal from "@/shared/components/Modal";
import { Button, Card } from "@/shared/components/ui";
import { formatNumber } from "@/shared/lib/format";

import FileImport from "@/features/quote/components/FileImport";
import QuoteForm from "@/features/quote/components/QuoteForm";
import QuoteTable from "@/features/quote/components/QuoteTable";
import { createQuote, deleteQuote, importQuotes, updateQuote } from "@/features/quote/api";

/**
 * Tab 2 — Quotes.
 *
 * The side-by-side table plus the two ways a quote gets in without the supplier
 * form: manual entry through the modal and bulk CSV/PDF import. Every mutation
 * refreshes the whole RFQ overview, because a new quote changes the counters,
 * the comparison and the dashboards — not just this table.
 */
function QuotesTab({ rfqId, quotes = [], onChanged }) {
  const [showQuoteForm, setShowQuoteForm] = useState(false);
  const [editingQuote, setEditingQuote] = useState(null);
  const [savingQuote, setSavingQuote] = useState(false);

  const [uploading, setUploading] = useState(false);

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
        await createQuote(rfqId, payload);
        toast.success("Supplier quote added successfully.");
      }

      setEditingQuote(null);
      setShowQuoteForm(false);

      await onChanged?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSavingQuote(false);
    }
  };

  const confirmDeleteQuote = async () => {
    if (!selectedQuote) return;

    try {
      setIsDeleting(true);

      await deleteQuote(selectedQuote.id);

      toast.success("Supplier quote deleted successfully.");

      setShowDeleteModal(false);
      setSelectedQuote(null);

      await onChanged?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleImport = async (file) => {
    try {
      setUploading(true);

      const result = await importQuotes(rfqId, file);

      // Both importers return { imported, failed, errors }.
      const imported = Number(result?.imported ?? 0);
      const failed = Number(result?.failed ?? 0);

      await onChanged?.();

      if (imported > 0) {
        toast.success(
          `Imported ${formatNumber(imported)} quote${imported === 1 ? "" : "s"}.`
        );
      }

      if (failed > 0) {
        const firstError = result?.errors?.[0];

        toast.warning(
          `${formatNumber(failed)} row${failed === 1 ? "" : "s"} could not be imported${
            firstError
              ? ` — ${firstError.error || firstError.message || firstError.reason || "see the file"}`
              : "."
          }`
        );
      }

      if (imported === 0 && failed === 0) {
        toast.info("Nothing new was found in that file.");
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setUploading(false);
    }
  };

  const complete = quotes.filter((quote) => quote.completeness === "complete").length;
  const incomplete = quotes.length - complete;

  return (
    <div className="space-y-5">
      <Card className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-content">
            Supplier quotes
          </h2>
          <p className="mt-0.5 text-xs text-muted">
            {formatNumber(quotes.length)} quote
            {quotes.length === 1 ? "" : "s"} · {formatNumber(complete)} complete
            {incomplete > 0 ? ` · ${formatNumber(incomplete)} incomplete` : ""}
          </p>
        </div>

        <Button
          size="sm"
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
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
          </svg>
          Add quote
        </Button>
      </Card>

      <QuoteTable
        quotes={quotes}
        onEdit={(quote) => {
          setEditingQuote(quote);
          setShowQuoteForm(true);
        }}
        onDelete={(quote) => {
          setSelectedQuote(quote);
          setShowDeleteModal(true);
        }}
      />

      <FileImport onUpload={handleImport} isUploading={uploading} />

      <Modal
        isOpen={showQuoteForm}
        onClose={() => {
          setShowQuoteForm(false);
          setEditingQuote(null);
        }}
        title={editingQuote ? "Edit Supplier Quote" : "Add Supplier Quote"}
        description={
          editingQuote
            ? "Update the figures the comparison engine will normalise."
            : "Use this for quotes that arrived by email or phone."
        }
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
        description={`Are you sure you want to delete the quote from "${selectedQuote?.supplier_name}"? The comparison will be recomputed without it.`}
        confirmText="Delete"
        isLoading={isDeleting}
      />
    </div>
  );
}

export default QuotesTab;
