import { useState } from "react";

import { toast } from "sonner";

import Modal from "@/shared/components/Modal";
import ConfirmModal from "@/shared/components/ConfirmModal";
import EmptyState from "@/shared/components/EmptyState";
import Loading from "@/shared/components/Loading";
import { Button } from "@/shared/components/ui";

import { createRFQ, deleteRFQ } from "../api";
import { useRFQs } from "../hooks";
import RFQCard from "../components/RFQCard";
import RFQForm from "../components/RFQForm";

function RFQListPage() {
  const { rfqs, loading, refresh } = useRFQs();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedRFQ, setSelectedRFQ] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleCreateRFQ = async (payload) => {
    try {
      setIsSubmitting(true);

      await createRFQ(payload);

      setShowCreateModal(false);

      toast.success("RFQ created successfully.");

      await refresh();
    } catch (error) {
      console.error(error);
      toast.error(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteRFQ = (rfq) => {
    setSelectedRFQ(rfq);
    setShowDeleteModal(true);
  };

  const confirmDeleteRFQ = async () => {
    if (!selectedRFQ) {
      return;
    }

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

  if (loading) {
    return <Loading message="Loading RFQs..." />;
  }

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
                {rfqs.length}
              </span>
            )}
          </div>

          <p className="mt-2 text-muted">
            Create RFQs and compare supplier quotes side by side.
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
          Create RFQ
        </Button>
      </div>

      {rfqs.length === 0 ? (
        <EmptyState
          title="No RFQs yet"
          description="Create your first RFQ to start collecting and comparing supplier quotes."
          action={
            <Button onClick={() => setShowCreateModal(true)}>
              Create your first RFQ
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:gap-5">
          {rfqs.map((rfq) => (
            <RFQCard key={rfq.id} rfq={rfq} onDelete={handleDeleteRFQ} />
          ))}
        </div>
      )}

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create RFQ"
      >
        <RFQForm
          onSubmit={handleCreateRFQ}
          onCancel={() => setShowCreateModal(false)}
          submitLabel="Create RFQ"
          isSubmitting={isSubmitting}
        />
      </Modal>

      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false);
          setSelectedRFQ(null);
        }}
        onConfirm={confirmDeleteRFQ}
        title="Delete RFQ"
        description={`Are you sure you want to delete "${selectedRFQ?.item_name}"? This will also remove all of its supplier quotes.`}
        confirmText="Delete"
        isLoading={isDeleting}
      />
    </div>
  );
}

export default RFQListPage;
