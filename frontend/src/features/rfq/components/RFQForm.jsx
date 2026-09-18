import { useState } from "react";

import { Button, FormField, inputClass } from "@/shared/components/ui";

const initialFormState = {
  item_name: "",
  specification: "",
  quantity: "",
  delivery_expectation: "",
  notes: "",
};

const errorClass = "border-danger/60 bg-danger-soft/40";

function RFQForm({
  initialValues = {},
  onSubmit,
  onCancel,
  submitLabel = "Save",
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

    if (!formData.item_name.trim()) {
      errs.item_name = "Item name is required";
    }

    if (!formData.specification.trim()) {
      errs.specification = "Material / Specification is required";
    }

    if (!formData.quantity || Number(formData.quantity) < 1) {
      errs.quantity = "Enter a valid quantity";
    }

    if (!formData.delivery_expectation) {
      errs.delivery_expectation = "Delivery expectation is required";
    }

    return errs;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }
    onSubmit({ ...formData, quantity: Number(formData.quantity) });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <FormField label="Item Name" required error={errors.item_name}>
        <input
          name="item_name"
          type="text"
          value={formData.item_name}
          onChange={handleChange}
          placeholder="e.g. Steel Bolt M10"
          className={`${inputClass} ${errors.item_name ? errorClass : ""}`}
        />
      </FormField>

      <div className="grid gap-5 sm:grid-cols-2">
        <FormField
          label="Material / Specification"
          required
          error={errors.specification}
        >
          <input
            name="specification"
            type="text"
            value={formData.specification}
            onChange={handleChange}
            placeholder="e.g. SS304"
            className={`${inputClass} ${
              errors.specification ? errorClass : ""
            }`}
          />
        </FormField>

        <FormField label="Quantity" required error={errors.quantity}>
          <input
            name="quantity"
            type="number"
            min="1"
            value={formData.quantity}
            onChange={handleChange}
            placeholder="e.g. 500"
            className={`${inputClass} ${errors.quantity ? errorClass : ""}`}
          />
        </FormField>
      </div>

      <FormField
        label="Delivery Expectation"
        required
        error={errors.delivery_expectation}
      >
        <input
          name="delivery_expectation"
          type="date"
          value={formData.delivery_expectation ?? ""}
          onChange={handleChange}
          className={`${inputClass} ${
            errors.delivery_expectation ? errorClass : ""
          }`}
        />
      </FormField>

      <FormField label="Notes" hint="optional">
        <textarea
          name="notes"
          rows={3}
          value={formData.notes}
          onChange={handleChange}
          placeholder="Additional requirements or context..."
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

export default RFQForm;
