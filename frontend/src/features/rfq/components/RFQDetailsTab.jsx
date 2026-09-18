import { useState } from "react";

import { toast } from "sonner";

import { Button, Card } from "@/shared/components/ui";
import { formatDateTime, formatFieldKey, formatNumber } from "@/shared/lib/format";
import { StatusBadge } from "@/shared/components/StatusBadge";

import { updateRFQ } from "../api";
import RFQForm from "./RFQForm";

/**
 * Tab 5 — RFQ details.
 *
 * The read-only grid of everything the RFQ carries, plus an inline editor that
 * PATCHes only the RFQ's own fields. The suppliers step is switched off here:
 * invitations are managed on the Suppliers tab, and re-submitting them from an
 * edit form would be a confusing second path to the same action.
 */
function RFQDetailsTab({ rfq, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSave = async (payload) => {
    try {
      setSaving(true);

      await updateRFQ(rfq.id, payload);

      toast.success("RFQ details updated.");

      setEditing(false);

      await onChanged?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-default bg-surface-2/50 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-content">RFQ details</h2>
            <p className="mt-0.5 text-xs text-muted">
              Created {formatDateTime(rfq.created_at)} · updated{" "}
              {formatDateTime(rfq.updated_at)}
            </p>
          </div>

          {!editing && (
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              Edit details
            </Button>
          )}
        </div>

        {editing ? (
          <div className="p-5">
            <RFQForm
              initialValues={rfq}
              onSubmit={handleSave}
              onCancel={() => setEditing(false)}
              submitLabel="Save changes"
              isSubmitting={saving}
              showSupplierStep={false}
            />
          </div>
        ) : (
          <dl className="grid grid-cols-1 gap-px bg-border-default sm:grid-cols-2 lg:grid-cols-4">
            <DetailItem label="RFQ number" value={rfq.rfq_number} />
            <DetailItem label="Status">
              <StatusBadge status={rfq.status} domain="rfq" />
            </DetailItem>
            <DetailItem label="Item" value={rfq.item_name} />
            <DetailItem label="Specification" value={rfq.specification} />
            <DetailItem
              label="Quantity"
              value={`${formatNumber(rfq.quantity)} ${rfq.unit || "pcs"}`}
            />
            <DetailItem label="Currency" value={rfq.currency} />
            <DetailItem label="Incoterms" value={rfq.incoterms || "—"} />
            <DetailItem label="Category" value={rfq.category || "—"} />
            <DetailItem
              label="Delivery expectation"
              value={rfq.delivery_expectation || "—"}
            />
            <DetailItem
              label="Quote deadline"
              value={rfq.deadline ? formatDateTime(rfq.deadline) : "—"}
            />
            <DetailItem label="Buyer company" value={rfq.buyer_company || "—"} />
            <DetailItem
              label="Ready to compare"
              value={rfq.ready_to_compare ? "Yes" : "Not yet"}
            />
            <DetailItem label="Notes" value={rfq.notes || "—"} span />
            <DetailItem label="Required fields" span>
              {rfq.required_fields?.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {rfq.required_fields.map((field) => (
                    <span
                      key={field}
                      className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-muted"
                    >
                      {formatFieldKey(field)}
                    </span>
                  ))}
                </div>
              ) : (
                "—"
              )}
            </DetailItem>
          </dl>
        )}
      </Card>
    </div>
  );
}

function DetailItem({ label, value, children, span = false }) {
  return (
    <div className={`bg-surface px-5 py-4 ${span ? "sm:col-span-2" : ""}`}>
      <dt className="text-xs font-medium uppercase tracking-wider text-subtle">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-medium text-content">
        {children ?? value}
      </dd>
    </div>
  );
}

export default RFQDetailsTab;
