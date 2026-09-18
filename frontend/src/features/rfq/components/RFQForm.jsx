import { useState } from "react";

import { Button, FormField, inputClass } from "@/shared/components/ui";

import RFQSupplierStep from "./RFQSupplierStep";

/**
 * Create/edit form for an RFQ.
 *
 * Used in two places, which is why the suppliers step is optional:
 *  - `CreateRFQPage` (and the list page's modal) renders the full form,
 *    including inline suppliers and the directory picker;
 *  - the detail page's "RFQ details" tab renders it with
 *    `showSupplierStep={false}` to PATCH the RFQ's own fields, since
 *    invitations are managed from the Suppliers tab instead.
 *
 * Numeric and datetime values are normalised on submit: `quantity` becomes a
 * number, `deadline` becomes an ISO string, and blank optional text becomes
 * `null` so the API clears the field rather than storing "".
 */

const initialFormState = {
  item_name: "",
  specification: "",
  quantity: "",
  unit: "pcs",
  currency: "USD",
  incoterms: "",
  delivery_expectation: "",
  deadline: "",
  category: "",
  notes: "",
};

const emptySupplierRow = {
  name: "",
  contact_email: "",
  contact_name: "",
  country: "",
  risk_rating: "low",
};

const errorClass = "border-danger/60 bg-danger-soft/40";

const CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD", "SGD", "AED"];

//: Free-text units with a datalist: buyers use units we cannot enumerate.
const COMMON_UNITS = [
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

const INCOTERMS = [
  "EXW",
  "FCA",
  "FOB",
  "CFR",
  "CIF",
  "CPT",
  "CIP",
  "DAP",
  "DPU",
  "DDP",
];

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** ISO datetime -> the "YYYY-MM-DDTHH:mm" shape `datetime-local` requires. */
function toDateTimeLocalValue(value) {
  if (!value) return "";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "";

  const pad = (part) => String(part).padStart(2, "0");

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate()
  )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function RFQForm({
  initialValues = {},
  onSubmit,
  onCancel,
  submitLabel = "Save",
  isSubmitting = false,
  showSupplierStep = true,
}) {
  const [formData, setFormData] = useState(() => ({
    ...initialFormState,
    ...initialValues,
    deadline: toDateTimeLocalValue(initialValues.deadline),
    notes: initialValues.notes ?? "",
  }));

  const [newSuppliers, setNewSuppliers] = useState(() =>
    showSupplierStep ? [{ ...emptySupplierRow }] : []
  );
  const [selectedSupplierIds, setSelectedSupplierIds] = useState([]);
  const [sendInvitations, setSendInvitations] = useState(true);
  const [errors, setErrors] = useState({});

  const clearError = (key) => {
    setErrors((prev) => {
      if (!prev[key]) return prev;

      const next = { ...prev };
      delete next[key];

      return next;
    });
  };

  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((prev) => ({ ...prev, [name]: value }));
    clearError(name);
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

    if (!formData.unit.trim()) {
      errs.unit = "Unit is required (e.g. pcs, kg)";
    }

    if (!formData.currency.trim() || formData.currency.trim().length !== 3) {
      errs.currency = "Use a 3-letter currency code";
    }

    if (!formData.delivery_expectation) {
      errs.delivery_expectation = "Delivery expectation is required";
    }

    // A deadline in the past would close the RFQ the moment it opens.
    if (formData.deadline && new Date(formData.deadline).getTime() < Date.now()) {
      errs.deadline = "Deadline must be in the future";
    }

    if (showSupplierStep) {
      newSuppliers.forEach((row, index) => {
        const hasContent = Object.values(row).some(
          (value) => String(value ?? "").trim() !== "" && value !== "low"
        );

        if (!hasContent) return;

        if (!row.name.trim()) {
          errs[`supplier.${index}.name`] = "Supplier name is required";
        }

        if (!row.contact_email.trim()) {
          errs[`supplier.${index}.contact_email`] =
            "An email is required — the form link is sent here";
        } else if (!EMAIL_PATTERN.test(row.contact_email.trim())) {
          errs[`supplier.${index}.contact_email`] = "Enter a valid email address";
        }
      });
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
      item_name: formData.item_name.trim(),
      specification: formData.specification.trim(),
      quantity: Number(formData.quantity),
      unit: formData.unit.trim(),
      currency: formData.currency.trim().toUpperCase(),
      // Optional text is sent as null so clearing a field actually clears it.
      incoterms: formData.incoterms.trim() || null,
      delivery_expectation: formData.delivery_expectation,
      deadline: formData.deadline
        ? new Date(formData.deadline).toISOString()
        : null,
      category: formData.category.trim() || null,
      notes: formData.notes.trim() || null,
    };

    if (showSupplierStep) {
      payload.new_suppliers = newSuppliers
        .filter((row) => row.name.trim() && row.contact_email.trim())
        .map((row) => ({
          name: row.name.trim(),
          contact_email: row.contact_email.trim(),
          contact_name: row.contact_name.trim() || null,
          country: row.country.trim() || null,
          risk_rating: row.risk_rating || "low",
        }));

      // Both lists go in one request: the API creates the inline suppliers and
      // issues every invitation (new + directory) together.
      payload.supplier_ids = selectedSupplierIds;
      payload.send_invitations = sendInvitations;
    }

    onSubmit(payload);
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
          placeholder="e.g. SS304, hot-rolled, 8.8 grade"
          className={`${inputClass} ${errors.specification ? errorClass : ""}`}
        />
      </FormField>

      <div className="grid gap-5 sm:grid-cols-3">
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

        <FormField label="Unit" required error={errors.unit}>
          <input
            name="unit"
            type="text"
            list="rfq-unit-options"
            value={formData.unit}
            onChange={handleChange}
            placeholder="pcs"
            className={`${inputClass} ${errors.unit ? errorClass : ""}`}
          />
          <datalist id="rfq-unit-options">
            {COMMON_UNITS.map((unit) => (
              <option key={unit} value={unit} />
            ))}
          </datalist>
        </FormField>

        <FormField
          label="Currency"
          hint="quotes are normalised to this"
          required
          error={errors.currency}
        >
          <select
            name="currency"
            value={formData.currency}
            onChange={handleChange}
            className={`${inputClass} ${errors.currency ? errorClass : ""}`}
          >
            {CURRENCIES.map((currency) => (
              <option key={currency} value={currency}>
                {currency}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <div className="grid gap-5 sm:grid-cols-3">
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

        <FormField
          label="Quote deadline"
          hint="optional"
          error={errors.deadline}
        >
          <input
            name="deadline"
            type="datetime-local"
            value={formData.deadline ?? ""}
            onChange={handleChange}
            className={`${inputClass} ${errors.deadline ? errorClass : ""}`}
          />
        </FormField>
      </div>

      <FormField label="Category" hint="optional">
        <input
          name="category"
          type="text"
          value={formData.category}
          onChange={handleChange}
          placeholder="e.g. Fasteners"
          className={inputClass}
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

      {showSupplierStep && (
        <RFQSupplierStep
          newSuppliers={newSuppliers}
          onNewSuppliersChange={setNewSuppliers}
          selectedSupplierIds={selectedSupplierIds}
          onSelectedSupplierIdsChange={setSelectedSupplierIds}
          sendInvitations={sendInvitations}
          onSendInvitationsChange={setSendInvitations}
          errors={errors}
          onClearError={clearError}
        />
      )}

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
