import { useState } from "react";

import { Button, FormField, inputClass } from "@/shared/components/ui";

/**
 * Manual quote entry / edit.
 *
 * Suppliers normally submit through their private form link, but a buyer still
 * needs to be able to type a quote in (a phone call, a PDF that failed the
 * importer) and to correct one. Every field the comparison engine consumes is
 * here — including the landed-cost components — because a quote that is missing
 * them is exactly the kind of quote the completeness check flags.
 *
 * Empty optional numbers are sent as `null`, not omitted: on an edit that is
 * what clears a value the buyer removed.
 */

const emptyFormState = {
  supplier_name: "",
  contact_email: "",
  unit_price: "",
  currency: "USD",
  unit: "pcs",
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
};

const errorClass = "border-danger/60 bg-danger-soft/40";

const CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD", "SGD", "AED"];

const UNITS = [
  "pcs",
  "kg",
  "ton",
  "m",
  "m2",
  "m3",
  "litre",
  "box",
  "carton",
  "pallet",
  "roll",
  "sheet",
  "set",
  "lot",
];

const INCOTERMS = ["EXW", "FCA", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"];

/** "" -> null, "12.5" -> 12.5. Keeps 0 (a free sample, no discount) meaningful. */
const optionalNumber = (value) => {
  const trimmed = String(value ?? "").trim();

  if (trimmed === "") return null;

  const parsed = Number(trimmed);

  return Number.isFinite(parsed) ? parsed : null;
};

function QuoteForm({
  initialValues = {},
  onSubmit,
  onCancel,
  submitLabel = "Save Quote",
  isSubmitting = false,
}) {
  const [formData, setFormData] = useState(() => {
    const merged = { ...emptyFormState };

    Object.keys(emptyFormState).forEach((key) => {
      const value = initialValues[key];

      merged[key] = value === null || value === undefined ? emptyFormState[key] : value;
    });

    return merged;
  });

  const [errors, setErrors] = useState({});

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
      errs.unit_price = "Enter a valid price";
    }

    if (formData.lead_time === "" || Number(formData.lead_time) < 0) {
      errs.lead_time = "Enter a valid lead time";
    }

    if (formData.contact_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.contact_email)) {
      errs.contact_email = "Enter a valid email address";
    }

    if (formData.moq !== "" && Number(formData.moq) < 0) {
      errs.moq = "MOQ cannot be negative";
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

    onSubmit({
      supplier_name: String(formData.supplier_name).trim(),
      contact_email: String(formData.contact_email).trim() || null,
      unit_price: Number(formData.unit_price),
      currency: formData.currency,
      unit: String(formData.unit).trim() || "pcs",
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
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <section className="space-y-5">
        <h3 className="text-sm font-semibold text-content">Supplier &amp; price</h3>

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField label="Supplier Name" required error={errors.supplier_name}>
            <input
              name="supplier_name"
              type="text"
              value={formData.supplier_name}
              onChange={handleChange}
              placeholder="e.g. ABC Metals Ltd."
              className={`${inputClass} ${errors.supplier_name ? errorClass : ""}`}
            />
          </FormField>

          <FormField label="Contact email" hint="optional" error={errors.contact_email}>
            <input
              name="contact_email"
              type="email"
              value={formData.contact_email}
              onChange={handleChange}
              placeholder="sales@abcmetals.com"
              className={`${inputClass} ${errors.contact_email ? errorClass : ""}`}
            />
          </FormField>
        </div>

        <div className="grid gap-5 sm:grid-cols-4">
          <FormField label="Unit Price" required error={errors.unit_price}>
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

          <FormField label="Currency">
            <select
              name="currency"
              value={formData.currency}
              onChange={handleChange}
              className={inputClass}
            >
              {CURRENCIES.map((currency) => (
                <option key={currency} value={currency}>
                  {currency}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Unit">
            <select
              name="unit"
              value={formData.unit}
              onChange={handleChange}
              className={inputClass}
            >
              {UNITS.map((unit) => (
                <option key={unit} value={unit}>
                  {unit}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Lead Time (Days)" required error={errors.lead_time}>
            <input
              name="lead_time"
              type="number"
              min="0"
              value={formData.lead_time}
              onChange={handleChange}
              placeholder="e.g. 14"
              className={`${inputClass} ${errors.lead_time ? errorClass : ""}`}
            />
          </FormField>
        </div>
      </section>

      <section className="space-y-5 border-t border-border-default pt-6">
        <h3 className="text-sm font-semibold text-content">Commercial terms</h3>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <FormField label="MOQ" hint="optional" error={errors.moq}>
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

          <FormField label="Incoterms" hint="optional">
            <select
              name="incoterms"
              value={formData.incoterms}
              onChange={handleChange}
              className={inputClass}
            >
              <option value="">Not specified</option>
              {INCOTERMS.map((incoterm) => (
                <option key={incoterm} value={incoterm}>
                  {incoterm}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Valid Until" hint="optional">
            <input
              name="validity_date"
              type="date"
              value={formData.validity_date}
              onChange={handleChange}
              className={inputClass}
            />
          </FormField>

          <FormField label="Warranty (months)" hint="optional">
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

      <section className="space-y-5 border-t border-border-default pt-6">
        <div>
          <h3 className="text-sm font-semibold text-content">
            Landed cost components
          </h3>
          <p className="mt-1 text-xs text-muted">
            Optional. Filling these in makes the normalised landed cost exact
            instead of estimated from the unit price.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-4">
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
