import { useState } from "react";

import { toast } from "sonner";

import { Button, Card } from "@/shared/components/ui";
import {
  formatDateTime,
  formatFieldKey,
  formatHours,
  formatNumber,
  formatPercentValue,
  formatRateBasis,
  toNumber,
} from "@/shared/lib/format";
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
 *
 * Services carry a second half — site, SLA, accreditations, GST — which is shown
 * only for a service RFQ and hidden for goods, matching the form that edits it.
 */
function RFQDetailsTab({ rfq, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const isGoods = rfq.procurement_type === "goods";
  const responseHours = toNumber(rfq.required_response_hours);
  const gstRate = toNumber(rfq.gst_rate);

  // The API sends the supplier-facing wording alongside the keys, in the same
  // order. Falling back to the key map only covers an older payload.
  const requiredLabels =
    rfq.required_field_labels?.length === rfq.required_fields?.length
      ? rfq.required_field_labels
      : (rfq.required_fields || []).map((field) => formatFieldKey(field));

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
            <DetailItem
              label="Procurement type"
              value={isGoods ? "Goods" : "Service"}
            />
            <DetailItem label="Category" value={rfq.category || "—"} />
            <DetailItem label="Scope" value={rfq.item_name} />
            <DetailItem label="Specification" value={rfq.specification} />
            <DetailItem
              label={isGoods ? "Quantity" : "Quantity / effort"}
              value={`${formatNumber(rfq.quantity)} ${
                isGoods ? rfq.unit || "" : formatRateBasis(rfq.unit)
              }`}
            />
            <DetailItem
              label={isGoods ? "Unit" : "Rate basis"}
              value={isGoods ? rfq.unit || "—" : formatRateBasis(rfq.unit)}
            />
            <DetailItem label="Currency" value={rfq.currency} />
            <DetailItem
              label="GST rate"
              value={gstRate === null ? "—" : formatPercentValue(gstRate)}
            />
            {isGoods ? (
              <DetailItem label="Incoterms" value={rfq.incoterms || "—"} />
            ) : (
              <DetailItem
                label="Required response time"
                value={responseHours === null ? "—" : formatHours(responseHours)}
              />
            )}
            <DetailItem
              label={isGoods ? "Delivery expectation" : "Works wanted by"}
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

            {!isGoods && (
              <>
                <DetailItem label="Site name" value={rfq.site_name || "—"} />
                <DetailItem label="Site address" value={rfq.site_address || "—"} />
                <DetailItem label="Site access notes" value={rfq.site_access_notes || "—"} span />
                <DetailItem label="Required accreditations" span>
                  {rfq.required_accreditations?.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {rfq.required_accreditations.map((accreditation) => (
                        <span
                          key={accreditation}
                          className="rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-medium text-primary-soft-fg"
                        >
                          {accreditation}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-subtle">
                      None required — compliance is not scored
                    </span>
                  )}
                </DetailItem>
              </>
            )}

            <DetailItem label="Notes" value={rfq.notes || "—"} span />
            <DetailItem label="Required fields" span>
              {requiredLabels.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {requiredLabels.map((label, index) => (
                    <span
                      key={`${rfq.required_fields?.[index] || label}-${index}`}
                      className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-muted"
                    >
                      {label}
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
