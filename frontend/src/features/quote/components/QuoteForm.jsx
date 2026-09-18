import { useState } from "react";

import { Button, FormField, inputClass } from "@/shared/components/ui";

const initialFormState = {
  supplier_name: "",
  unit_price: "",
  currency: "USD",
  lead_time: "",
  payment_terms: "",
  remarks: "",
};

const errorClass = "border-danger/60 bg-danger-soft/40";

const CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD", "SGD", "AED"];

function QuoteForm({
  initialValues = {},
  onSubmit,
  onCancel,
  submitLabel = "Save Quote",
  isSubmitting = false,
}) {
  const [formData, setFormData] = useState({
    ...initialFormState,
    ...initialValues,
  });
  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: null }));
  };

  const validate = () => {
    const errs = {};
    if (!formData.supplier_name.trim())
      errs.supplier_name = "Supplier name is required";
    if (!formData.unit_price || Number(formData.unit_price) <= 0)
      errs.unit_price = "Enter a valid price";
    if (!formData.lead_time || Number(formData.lead_time) < 0)
      errs.lead_time = "Enter a valid lead time";
    return errs;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }
    onSubmit({
      ...formData,
      unit_price: Number(formData.unit_price),
      lead_time: Number(formData.lead_time),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
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

      <div className="grid gap-5 sm:grid-cols-2">
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
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
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
      </div>

      <FormField label="Remarks" hint="optional">
        <textarea
          name="remarks"
          rows={3}
          value={formData.remarks}
          onChange={handleChange}
          placeholder="Any additional notes about this quote..."
          className={`${inputClass} resize-none`}
        />
      </FormField>

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
