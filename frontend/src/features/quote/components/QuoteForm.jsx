import { useState } from "react";

import ChipMultiSelect from "@/shared/components/ChipMultiSelect";
import { Button, FormField, Select, inputClass } from "@/shared/components/ui";

import { currencyOptions } from "@/features/meta/currencies";
import { useMetaOptions } from "@/features/meta/hooks";

/**
 * Manual quote entry / edit.
 *
 * Suppliers normally submit through their private form link, but a buyer still
 * needs to be able to type a quote in (a phone call, a PDF that failed the
 * importer) and to correct one. Every field the comparison engine consumes is
 * here — including the landed-cost components — because a quote that is missing
 * them is exactly the kind of quote the completeness check flags.
 *
 * The form follows the RFQ's procurement type. A service quote leads with the
 * rate, the basis it is quoted against (per job, per hour, per point) and the
 * response time, then the callout/attendance charge and GST; Incoterms, MOQ and
 * freight retreat into a collapsed "additional (goods)" group, because on a
 * maintenance job they are not asked for and showing them invites a supplier to
 * leave a goods field blank that nobody wanted. For goods the same group is
 * expanded and required, since that is the contract the goods weights expect.
 *
 * Empty optional numbers are sent as `null`, not omitted: on an edit that is
 * what clears a value the buyer removed.
 */

const emptyFormState = {
  supplier_name: "",
  contact_email: "",
  unit_price: "",
  currency: "",
  unit: "",
  lead_time: "",
  moq: "",
  payment_terms: "",
  incoterms: "",
  validity_date: "",
  warranty_months: "",
  shipping_cost: "",
  duties: "",
  taxes: "",
  discount: "",
  notes: "",
  remarks: "",
  // ---- services ----------------------------------------------------------
  response_time_hours: "",
  callout_charge: "",
  labour_rate: "",
  materials_markup_pct: "",
  compliance_accreditations: [],
  gst_rate: "",
};

const errorClass = "border-danger/60 bg-danger-soft/40";

const INCOTERMS = ["EXW", "FCA", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"];

/** "" -> null, "12.5" -> 12.5. Keeps 0 (a free sample, no discount) meaningful. */
const optionalNumber = (value) => {
  const trimmed = String(value ?? "").trim();

  if (trimmed === "") return null;

  const parsed = Number(trimmed);

  return Number.isFinite(parsed) ? parsed : null;
};

/** Decimal fields travel as strings: 9 -> "9.00". */
const optionalDecimalString = (value) => {
  const parsed = optionalNumber(value);

  return parsed === null ? null : parsed.toFixed(2);
};

/** "" -> null, "4" -> 4. */
const optionalInteger = (value) => {
  const parsed = optionalNumber(value);

  return parsed === null ? null : Math.trunc(parsed);
};

function QuoteForm({
  initialValues = {},
  onSubmit,
  onCancel,
  submitLabel = "Save Quote",
  isSubmitting = false,
  procurementType = "",
  rfqCurrency = "",
  rfqUnit = "",
}) {
  const { options: meta } = useMetaOptions();

  // Anything that is not goods is quoted like a service: that is the product's
  // default, and a service-flavoured form is the safe reading of an unknown type.
  const isGoods = procurementType === "goods";

  const [formData, setFormData] = useState(() => {
    const merged = { ...emptyFormState };

    Object.keys(emptyFormState).forEach((key) => {
      const value = initialValues[key];

      if (value === null || value === undefined) return;

      merged[key] = value;
    });

    // Decimal strings ("9.00") would render with their padding in a number input.
    merged.gst_rate = optionalNumber(initialValues.gst_rate) ?? "";
    merged.materials_markup_pct = optionalNumber(initialValues.materials_markup_pct) ?? "";
    merged.response_time_hours = optionalNumber(initialValues.response_time_hours) ?? "";
    merged.compliance_accreditations = Array.isArray(initialValues.compliance_accreditations)
      ? [...initialValues.compliance_accreditations]
      : [];

    // The RFQ's own vocabulary seeds the two pickers the buyer would otherwise
    // have to guess: what the rate is per, and which currency it is in. The RFQ's
    // rate basis wins over the taxonomy's first entry, because the quote is an
    // answer to *that* RFQ.
    if (!merged.currency) merged.currency = rfqCurrency || meta?.base_currency || "";

    if (!merged.unit) {
      const bases = (isGoods ? meta?.goods_units : meta?.service_rate_bases) || [];

      merged.unit = rfqUnit || bases[0] || "";
    }

    return merged;
  });

  const [showGoodsGroup, setShowGoodsGroup] = useState(isGoods);
  const [errors, setErrors] = useState({});

  const rateBases = (isGoods ? meta?.goods_units : meta?.service_rate_bases) || [];
  const rateBasisOptions = !formData.unit || rateBases.includes(formData.unit)
    ? rateBases
    : [formData.unit, ...rateBases];

  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: null }));
  };

  const validate = () => {
    const errs = {};

    if (!String(formData.supplier_name).trim()) {
      errs.supplier_name = "Supplier name is required";
    }

    if (formData.unit_price === "" || Number(formData.unit_price) <= 0) {
      errs.unit_price = "Enter a valid rate";
    }

    // Mobilisation is required by the API on every quote and is scored for
    // services too (it is how long until work can start), so the form asks for it
    // in both modes rather than letting the request fail with a 422. Only the
    // wording changes: "lead time" is a production term.
    if (formData.lead_time === "" || Number(formData.lead_time) < 0) {
      errs.lead_time = isGoods
        ? "Enter a valid lead time"
        : "Enter the mobilisation time (use 0 for same-day attendance)";
    }

    if (formData.contact_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.contact_email)) {
      errs.contact_email = "Enter a valid email address";
    }

    if (formData.moq !== "" && Number(formData.moq) < 0) {
      errs.moq = "MOQ cannot be negative";
    }

    if (formData.response_time_hours !== "" && Number(formData.response_time_hours) < 0) {
      errs.response_time_hours = "Response time cannot be negative";
    }

    if (formData.materials_markup_pct !== "") {
      const markup = Number(formData.materials_markup_pct);

      if (!Number.isFinite(markup) || markup < 0) {
        errs.materials_markup_pct = "Enter a markup percentage";
      }
    }

    if (formData.gst_rate !== "") {
      const gst = Number(formData.gst_rate);

      if (!Number.isFinite(gst) || gst < 0 || gst > 100) {
        errs.gst_rate = "GST must be between 0 and 100";
      }
    }

    return errs;
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    const errs = validate();

    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }

    const payload = {
      supplier_name: String(formData.supplier_name).trim(),
      contact_email: String(formData.contact_email).trim() || null,
      unit_price: Number(formData.unit_price),
      currency: String(formData.currency).trim(),
      unit: String(formData.unit).trim(),
      lead_time: Number(formData.lead_time),
      moq: optionalNumber(formData.moq),
      payment_terms: String(formData.payment_terms).trim() || null,
      incoterms: formData.incoterms || null,
      validity_date: formData.validity_date || null,
      warranty_months: optionalNumber(formData.warranty_months),
      shipping_cost: optionalNumber(formData.shipping_cost),
      duties: optionalNumber(formData.duties),
      taxes: optionalNumber(formData.taxes),
      discount: optionalNumber(formData.discount),
      notes: String(formData.notes).trim() || null,
      remarks: String(formData.remarks).trim() || null,

      // ---- services ------------------------------------------------------
      response_time_hours: optionalInteger(formData.response_time_hours),
      callout_charge: optionalDecimalString(formData.callout_charge),
      labour_rate: optionalDecimalString(formData.labour_rate),
      materials_markup_pct: optionalDecimalString(formData.materials_markup_pct),
      compliance_accreditations: formData.compliance_accreditations,
      gst_rate: optionalDecimalString(formData.gst_rate),
    };

    // `currency` and `unit` are non-nullable on the quote table and required on
    // create. Sending null would either fail validation or try to write NULL into
    // a NOT NULL column, so an empty value is omitted: the API's own default
    // covers create, and `exclude_unset` leaves the stored value alone on update.
    if (!payload.currency) delete payload.currency;
    if (!payload.unit) delete payload.unit;

    onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <section className="space-y-5">
        <h3 className="text-sm font-semibold text-content">
          Supplier &amp; {isGoods ? "price" : "rate"}
        </h3>

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField label="Supplier Name" required error={errors.supplier_name}>
            <input
              name="supplier_name"
              type="text"
              value={formData.supplier_name}
              onChange={handleChange}
              placeholder="e.g. ABC Facilities Pte Ltd"
              className={`${inputClass} ${errors.supplier_name ? errorClass : ""}`}
            />
          </FormField>

          <FormField label="Contact email" hint="optional" error={errors.contact_email}>
            <input
              name="contact_email"
              type="email"
              value={formData.contact_email}
              onChange={handleChange}
              placeholder="sales@abcfacilities.sg"
              className={`${inputClass} ${errors.contact_email ? errorClass : ""}`}
            />
          </FormField>
        </div>

        <div className="grid gap-5 sm:grid-cols-4">
          <FormField
            label={isGoods ? "Unit price" : "Rate"}
            required
            error={errors.unit_price}
          >
            <input
              name="unit_price"
              type="number"
              min="0"
              step="0.01"
              value={formData.unit_price}
              onChange={handleChange}
              placeholder="0.00"
              className={`${inputClass} ${errors.unit_price ? errorClass : ""}`}
            />
          </FormField>

          <FormField
            label={isGoods ? "Unit" : "Rate basis"}
            hint={isGoods ? undefined : "what the rate is per"}
          >
            <Select
              name="unit"
              options={rateBasisOptions}
              value={formData.unit}
              onChange={handleChange}
              placeholder={isGoods ? "pcs" : "per job"}
            />
          </FormField>

          <FormField label="Currency">
            <Select
              name="currency"
              options={currencyOptions(rfqCurrency, meta?.base_currency, formData.currency)}
              value={formData.currency}
              onChange={handleChange}
            />
          </FormField>

          <FormField
            label={isGoods ? "Lead time (days)" : "Mobilisation (days)"}
            hint={isGoods ? undefined : "how long until work starts"}
            required
            error={errors.lead_time}
          >
            <input
              name="lead_time"
              type="number"
              min="0"
              value={formData.lead_time}
              onChange={handleChange}
              placeholder={isGoods ? "e.g. 14" : "e.g. 3"}
              className={`${inputClass} ${errors.lead_time ? errorClass : ""}`}
            />
          </FormField>
        </div>

        {!isGoods && (
          <div className="grid gap-5 sm:grid-cols-3">
            <FormField
              label="Response time (hours)"
              hint="SLA to attend site"
              error={errors.response_time_hours}
            >
              <input
                name="response_time_hours"
                type="number"
                min="0"
                value={formData.response_time_hours}
                onChange={handleChange}
                placeholder="e.g. 4"
                className={`${inputClass} ${
                  errors.response_time_hours ? errorClass : ""
                }`}
              />
            </FormField>

            {/* Surfaced separately from the rate on purpose: attendance is billed
                whether or not the works proceed, so a cheap rate with a large
                callout can still be the expensive supplier. */}
            <FormField
              label="Callout / attendance charge"
              hint="per attendance"
            >
              <input
                name="callout_charge"
                type="number"
                min="0"
                step="0.01"
                value={formData.callout_charge}
                onChange={handleChange}
                placeholder="0.00"
                className={inputClass}
              />
            </FormField>

            <FormField label="Labour rate (per hour)">
              <input
                name="labour_rate"
                type="number"
                min="0"
                step="0.01"
                value={formData.labour_rate}
                onChange={handleChange}
                placeholder="0.00"
                className={inputClass}
              />
            </FormField>
          </div>
        )}

        {!isGoods && (
          <div className="grid gap-5 sm:grid-cols-3">
            <FormField
              label="Materials markup (%)"
              hint="above cost"
              error={errors.materials_markup_pct}
            >
              <input
                name="materials_markup_pct"
                type="number"
                min="0"
                step="0.01"
                value={formData.materials_markup_pct}
                onChange={handleChange}
                placeholder="e.g. 15"
                className={`${inputClass} ${
                  errors.materials_markup_pct ? errorClass : ""
                }`}
              />
            </FormField>

            <FormField
              label="GST rate (%)"
              hint="leave blank if a tax amount is given"
              error={errors.gst_rate}
            >
              <input
                name="gst_rate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formData.gst_rate}
                onChange={handleChange}
                placeholder="9"
                className={`${inputClass} ${errors.gst_rate ? errorClass : ""}`}
              />
            </FormField>
          </div>
        )}
      </section>

      {!isGoods && (
        <section className="space-y-5 border-t border-border-default pt-6">
          <div>
            <h3 className="text-sm font-semibold text-content">
              Accreditations &amp; licences
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              What this supplier holds. Any licence the RFQ required but this list
              does not contain caps the compliance score, because the work may not
              lawfully proceed without it.
            </p>
          </div>

          <ChipMultiSelect
            options={meta?.common_accreditations || []}
            value={formData.compliance_accreditations}
            onChange={(next) =>
              setFormData((prev) => ({ ...prev, compliance_accreditations: next }))
            }
            placeholder="Add a licence or certification…"
          />
        </section>
      )}

      <section className="space-y-5 border-t border-border-default pt-6">
        <h3 className="text-sm font-semibold text-content">Commercial terms</h3>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <FormField label="Payment Terms" hint="optional">
            <input
              name="payment_terms"
              type="text"
              value={formData.payment_terms}
              onChange={handleChange}
              placeholder="e.g. Net 30"
              className={inputClass}
            />
          </FormField>

          <FormField
            label={isGoods ? "Valid until" : "Rates valid until"}
            hint="optional"
          >
            <input
              name="validity_date"
              type="date"
              value={formData.validity_date}
              onChange={handleChange}
              className={inputClass}
            />
          </FormField>

          <FormField
            label={isGoods ? "Warranty (months)" : "Defect liability (months)"}
            hint="optional"
          >
            <input
              name="warranty_months"
              type="number"
              min="0"
              value={formData.warranty_months}
              onChange={handleChange}
              placeholder="e.g. 12"
              className={inputClass}
            />
          </FormField>
        </div>
      </section>

      {/* Goods-shaped fields. Collapsed for a service RFQ: nothing is shipped and
          no Incoterm applies, but a supplier who volunteers a freight figure can
          still be recorded without leaving the form. */}
      <section className="space-y-5 border-t border-border-default pt-6">
        <button
          type="button"
          onClick={() => setShowGoodsGroup((prev) => !prev)}
          aria-expanded={showGoodsGroup}
          className="flex w-full items-center justify-between gap-3 text-left"
        >
          <span>
            <span className="text-sm font-semibold text-content">
              Additional (goods)
            </span>
            <span className="mt-1 block text-xs leading-relaxed text-muted">
              MOQ, Incoterms and freight. Not part of a service quote — the minimum
              callout is the callout charge above.
            </span>
          </span>

          <svg
            className={`h-4 w-4 shrink-0 text-subtle transition ${
              showGoodsGroup ? "rotate-180" : ""
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showGoodsGroup && (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <FormField
              label={isGoods ? "MOQ" : "Minimum callout / order"}
              hint="optional"
              error={errors.moq}
            >
              <input
                name="moq"
                type="number"
                min="0"
                value={formData.moq}
                onChange={handleChange}
                placeholder="e.g. 250"
                className={`${inputClass} ${errors.moq ? errorClass : ""}`}
              />
            </FormField>

            <FormField label="Incoterms" hint="optional">
              <Select
                name="incoterms"
                options={INCOTERMS}
                allowEmpty
                value={formData.incoterms}
                onChange={handleChange}
              />
            </FormField>

            <FormField label="Shipping" hint="optional">
              <input
                name="shipping_cost"
                type="number"
                min="0"
                step="0.01"
                value={formData.shipping_cost}
                onChange={handleChange}
                placeholder="0.00"
                className={inputClass}
              />
            </FormField>

            <FormField label="Duties" hint="optional">
              <input
                name="duties"
                type="number"
                min="0"
                step="0.01"
                value={formData.duties}
                onChange={handleChange}
                placeholder="0.00"
                className={inputClass}
              />
            </FormField>

            <FormField label="Taxes" hint="optional">
              <input
                name="taxes"
                type="number"
                min="0"
                step="0.01"
                value={formData.taxes}
                onChange={handleChange}
                placeholder="0.00"
                className={inputClass}
              />
            </FormField>

            <FormField label="Discount" hint="optional">
              <input
                name="discount"
                type="number"
                min="0"
                step="0.01"
                value={formData.discount}
                onChange={handleChange}
                placeholder="0.00"
                className={inputClass}
              />
            </FormField>
          </div>
        )}
      </section>

      <section className="space-y-5 border-t border-border-default pt-6">
        <FormField label="Notes" hint="optional">
          <textarea
            name="notes"
            rows={2}
            value={formData.notes}
            onChange={handleChange}
            placeholder="Anything the supplier attached to the quote..."
            className={`${inputClass} resize-none`}
          />
        </FormField>

        <FormField label="Remarks" hint="optional">
          <textarea
            name="remarks"
            rows={2}
            value={formData.remarks}
            onChange={handleChange}
            placeholder="Your own notes about this quote..."
            className={`${inputClass} resize-none`}
          />
        </FormField>
      </section>

      <div className="flex items-center justify-end gap-3 pt-2">
        {onCancel && (
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" loading={isSubmitting} loadingText="Saving…">
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

export default QuoteForm;
