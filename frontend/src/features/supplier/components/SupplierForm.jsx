import { useState } from "react";

import { Button, FormField, inputClass } from "@/shared/components/ui";
import { RISK_RATING_OPTIONS } from "@/shared/lib/status";

/*
 * Create/edit form for one supplier record.
 *
 * Every field the API accepts as a string is a string here — nothing is cast to
 * a number, because phone numbers, postal codes and external references all
 * lose information when they pass through a numeric type. Values are trimmed on
 * submit so a stray space can never become a "different" supplier.
 */

const initialFormState = {
  name: "",
  contact_name: "",
  contact_email: "",
  phone: "",
  website: "",
  country: "",
  city: "",
  risk_rating: "low",
  external_ref: "",
  notes: "",
};

const errorClass = "border-danger/60 bg-danger-soft/40";

// Deliberately permissive: enough to catch typos, not enough to reject a valid
// but unusual address. The server is the real authority.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Build the form state from `initialValues`, ignoring any key the form does not
 * own. The directory list payload carries read-only fields (`id`, `created_at`,
 * the invitation counters); spreading them in would then post them back.
 */
function buildFormState(initialValues) {
  const state = { ...initialFormState };

  Object.keys(initialFormState).forEach((key) => {
    const value = initialValues[key];

    if (value !== null && value !== undefined) {
      state[key] = value;
    }
  });

  return state;
}

function SupplierForm({
  initialValues = {},
  onSubmit,
  onCancel,
  submitLabel = "Save supplier",
  isSubmitting = false,
}) {
  const [formData, setFormData] = useState(() => buildFormState(initialValues));
  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: null }));
  };

  const validate = () => {
    const errs = {};

    if (!formData.name.trim()) {
      errs.name = "Supplier name is required";
    }

    const email = formData.contact_email.trim();

    if (!email) {
      errs.contact_email = "Contact email is required";
    } else if (!EMAIL_PATTERN.test(email)) {
      errs.contact_email = "Enter a valid email address";
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

    const payload = {};

    Object.entries(formData).forEach(([key, value]) => {
      payload[key] = typeof value === "string" ? value.trim() : value;
    });

    onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <FormField label="Supplier Name" required error={errors.name}>
        <input
          name="name"
          type="text"
          value={formData.name}
          onChange={handleChange}
          placeholder="e.g. Nordic Steel Works"
          className={`${inputClass} ${errors.name ? errorClass : ""}`}
        />
      </FormField>

      <div className="grid gap-5 sm:grid-cols-2">
        <FormField label="Contact Name" hint="optional">
          <input
            name="contact_name"
            type="text"
            value={formData.contact_name}
            onChange={handleChange}
            placeholder="e.g. Ana Lindqvist"
            className={inputClass}
          />
        </FormField>

        <FormField label="Contact Email" required error={errors.contact_email}>
          <input
            name="contact_email"
            type="email"
            value={formData.contact_email}
            onChange={handleChange}
            placeholder="e.g. quotes@nordicsteel.com"
            className={`${inputClass} ${
              errors.contact_email ? errorClass : ""
            }`}
          />
        </FormField>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <FormField label="Phone" hint="optional">
          <input
            name="phone"
            type="text"
            value={formData.phone}
            onChange={handleChange}
            placeholder="e.g. +46 8 123 456"
            className={inputClass}
          />
        </FormField>

        <FormField label="Website" hint="optional">
          <input
            name="website"
            type="text"
            value={formData.website}
            onChange={handleChange}
            placeholder="e.g. nordicsteel.com"
            className={inputClass}
          />
        </FormField>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <FormField label="Country" hint="optional">
          <input
            name="country"
            type="text"
            value={formData.country}
            onChange={handleChange}
            placeholder="e.g. Sweden"
            className={inputClass}
          />
        </FormField>

        <FormField label="City" hint="optional">
          <input
            name="city"
            type="text"
            value={formData.city}
            onChange={handleChange}
            placeholder="e.g. Gothenburg"
            className={inputClass}
          />
        </FormField>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <FormField label="Risk Rating" hint="drives sourcing decisions">
          <select
            name="risk_rating"
            value={formData.risk_rating}
            onChange={handleChange}
            className={inputClass}
          >
            {RISK_RATING_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </FormField>

        <FormField label="External Reference" hint="optional">
          <input
            name="external_ref"
            type="text"
            value={formData.external_ref}
            onChange={handleChange}
            placeholder="e.g. ERP-00123"
            className={inputClass}
          />
        </FormField>
      </div>

      <FormField label="Notes" hint="optional">
        <textarea
          name="notes"
          rows={3}
          value={formData.notes}
          onChange={handleChange}
          placeholder="Payment terms, certifications, past performance..."
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

export default SupplierForm;
