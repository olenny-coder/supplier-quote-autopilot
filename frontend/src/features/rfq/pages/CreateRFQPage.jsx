import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { toast } from "sonner";

import { Card } from "@/shared/components/ui";

import { createRFQ } from "../api";
import RFQForm from "../components/RFQForm";

function CreateRFQPage() {
  const navigate = useNavigate();

  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCreateRFQ = async (payload) => {
    try {
      setIsSubmitting(true);

      const createdRFQ = await createRFQ(payload);

      navigate(`/rfqs/${createdRFQ.id}`);
    } catch (error) {
      console.error(error);
      toast.error(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
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
          Create a new Request for Quotation to start collecting supplier quotes.
        </p>
      </div>

      <Card className="p-6 sm:p-8">
        <RFQForm
          onSubmit={handleCreateRFQ}
          onCancel={() => navigate("/")}
          submitLabel="Create RFQ"
          isSubmitting={isSubmitting}
        />
      </Card>
    </div>
  );
}

export default CreateRFQPage;
