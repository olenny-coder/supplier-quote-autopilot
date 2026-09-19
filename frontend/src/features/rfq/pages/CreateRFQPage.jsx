import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { toast } from "sonner";

import { Card } from "@/shared/components/ui";

import { createRFQ } from "../api";
import RFQForm from "../components/RFQForm";

/**
 * Full-page RFQ creation.
 *
 * A page rather than a modal since the form carries a suppliers step: the
 * buyer adds up to three suppliers inline, picks any that already exist in the
 * directory, and every one of them is issued a private form link in the same
 * request.
 */
function CreateRFQPage() {
  const navigate = useNavigate();

  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCreateRFQ = async (payload) => {
    try {
      setIsSubmitting(true);

      const createdRFQ = await createRFQ(payload);

      const invited =
        (payload.new_suppliers?.length || 0) + (payload.supplier_ids?.length || 0);

      toast.success(
        invited
          ? `RFQ ${createdRFQ.rfq_number} created with ${invited} supplier${
              invited === 1 ? "" : "s"
            }.`
          : `RFQ ${createdRFQ.rfq_number} created.`
      );

      if (!payload.send_invitations && invited) {
        toast.warning("Invitations saved but not emailed — send them from the RFQ page.");
      }

      navigate(`/rfqs/${createdRFQ.id}`);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Link
          to="/rfqs"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-muted transition hover:text-content"
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
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back to RFQs
        </Link>

        <h1 className="mt-4 text-2xl font-bold tracking-tight text-content sm:text-3xl">
          Create RFQ
        </h1>

        <p className="mt-2 text-muted">
          Describe the works or the goods, set what a complete quote has to
          contain, and add the suppliers you want rates from — each one gets their
          own private form link. Maintenance and minor works are the default;
          switch to goods for a supply order.
        </p>
      </div>

      <Card className="p-6 sm:p-8">
        <RFQForm
          onSubmit={handleCreateRFQ}
          onCancel={() => navigate("/rfqs")}
          submitLabel="Create RFQ"
          isSubmitting={isSubmitting}
        />
      </Card>
    </div>
  );
}

export default CreateRFQPage;
