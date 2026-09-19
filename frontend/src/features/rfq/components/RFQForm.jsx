import { useEffect, useState } from "react";

import ChipMultiSelect from "@/shared/components/ChipMultiSelect";
import { Button, FormField, Select, inputClass } from "@/shared/components/ui";
import { formatFieldKey, toNumber } from "@/shared/lib/format";

import { currencyOptions } from "@/features/meta/currencies";
import { useMetaOptions } from "@/features/meta/hooks";

import RFQSupplierStep from "./RFQSupplierStep";

/**
 * Create/edit form for an RFQ — now a *procurement* form, not a goods form.
 *
 * Used in two places, which is why the suppliers step is optional:
 *  - `CreateRFQPage` renders the full form, including inline suppliers and the
 *    directory picker;
 *  - the detail page's "RFQ details" tab renders it with
 *    `showSupplierStep={false}` to PATCH the RFQ's own fields, since
 *    invitations are managed from the Suppliers tab instead.
 *
 * Everything selectable comes from `GET /meta/options`: the procurement types,
 * the service/goods categories, the rate bases, the accreditation list, the
 * required-field contract, the base currency (SGD) and the default GST rate.
 * The form therefore has no taxonomy of its own, and adding a service category is
 * a backend-only change.
 *
 * The goods path is kept whole: with `procurement_type === "goods"` the service
 * fields (site, SLA, accreditations, GST hint) disappear and Incoterms / MOQ /
 * lead time come back, which is the contract the goods scoring weights expect.
 *
 * Values are normalised on submit: numbers become numbers, `gst_rate` becomes a
 * decimal *string* (the API serialises Decimal that way and accepts one back),
 * and blank optional text becomes `null` so clearing a field actually clears it.
 */

const initialFormState = {
  procurement_type: "",
  item_name: "",
  specification: "",
  quantity: "",
  unit: "",
  currency: "",
  incoterms: "",
  delivery_expectation: "",
  deadline: "",
  category: "",
  notes: "",
  // ---- services ----------------------------------------------------------
  site_name: "",
  site_address: "",
  site_access_notes: "",
  required_response_hours: "",
  required_accreditations: [],
  gst_rate: "",
};

const emptySupplierRow = {
  name: "",
  contact_email: "",
  contact_name: "",
  country: "",
  risk_rating: "low",
};

const errorClass = "border-danger/60 bg-danger-soft/40";

//: Incoterms are a fixed ICC vocabulary and are not part of `/meta/options`
//: (they are goods-only and the taxonomy endpoint does not carry them), so this
//: one list stays local. It is hidden entirely for services.
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

/** "" -> null, "12" -> 12. Keeps 0 meaningful (a zero response time is a promise). */
function optionalInteger(value) {
  const trimmed = String(value ?? "").trim();

  if (trimmed === "") return null;

  const parsed = Number(trimmed);

  return Number.isFinite(parsed) ? Math.trunc(parsed) : null;
}

/** API values -> form values. `null` text becomes "", `null` arrays become []. */
function toFormValues(initialValues) {
  const text = (key) => {
    const value = initialValues[key];

    return value === null || value === undefined ? "" : String(value);
  };

  const gstRate = toNumber(initialValues.gst_rate);

  return {
    ...initialFormState,
    procurement_type: text("procurement_type"),
    item_name: text("item_name"),
    specification: text("specification"),
    quantity: initialValues.quantity ?? "",
    unit: text("unit"),
    currency: text("currency"),
    incoterms: text("incoterms"),
    delivery_expectation: text("delivery_expectation"),
    deadline: toDateTimeLocalValue(initialValues.deadline),
    category: text("category"),
    notes: text("notes"),
    site_name: text("site_name"),
    site_address: text("site_address"),
    site_access_notes: text("site_access_notes"),
    required_response_hours: initialValues.required_response_hours ?? "",
    required_accreditations: Array.isArray(initialValues.required_accreditations)
      ? [...initialValues.required_accreditations]
      : [],
    gst_rate: gstRate === null ? "" : String(gstRate),
  };
}

function RFQForm({
  initialValues = {},
  onSubmit,
  onCancel,
  submitLabel = "Save",
  isSubmitting = false,
  showSupplierStep = true,
}) {
  const { options: meta, error: metaError } = useMetaOptions();

  // An edit carries the record's own values, so the per-type defaults below must
  // never be injected over them: a buyer who cleared GST means it.
  const isEdit = Boolean(initialValues.id);

  const [formData, setFormData] = useState(() => toFormValues(initialValues));

  const [requiredFields, setRequiredFields] = useState(() =>
    Array.isArray(initialValues.required_fields)
      ? [...initialValues.required_fields]
      : []
  );
  const [requiredFieldsSeeded, setRequiredFieldsSeeded] = useState(
    () =>
      Array.isArray(initialValues.required_fields) &&
      initialValues.required_fields.length > 0
  );

  const [newSuppliers, setNewSuppliers] = useState(() =>
    showSupplierStep ? [{ ...emptySupplierRow }] : []
  );
  const [selectedSupplierIds, setSelectedSupplierIds] = useState([]);
  const [sendInvitations, setSendInvitations] = useState(true);
  const [errors, setErrors] = useState({});

  const isGoods = formData.procurement_type === "goods";

  const categories = (isGoods ? meta?.goods_categories : meta?.service_categories) || [];
  const rateBases = (isGoods ? meta?.goods_units : meta?.service_rate_bases) || [];
  const requiredFieldOptions = meta?.required_fields?.[formData.procurement_type] || [];

  // A record edited after the taxonomy changed (a legacy goods RFQ whose unit is
  // not a current rate basis) must still display its own value rather than
  // silently showing the first option while the state holds something else.
  const withCurrentValue = (options, current) =>
    !current || options.includes(current) ? options : [current, ...options];

  const categoryOptions = withCurrentValue(categories, formData.category);
  const rateBasisOptions = withCurrentValue(rateBases, formData.unit);

  /** Supplier-facing wording, from the API, so this file owns no vocabulary. */
  const labelFor = (key) => meta?.required_field_labels?.[key] || formatFieldKey(key);

  // Seed the API's own defaults (procurement type, base currency, GST rate, first
  // rate basis) once the taxonomy lands. `isEdit` guards it, so opening an
  // existing RFQ never has its values rewritten by a default.
  useEffect(() => {
    if (isEdit || !meta) return;

    setFormData((prev) => {
      const next = { ...prev };
      let changed = false;

      if (!next.procurement_type && meta.default_procurement_type) {
        next.procurement_type = meta.default_procurement_type;
        changed = true;
      }

      if (!next.currency && meta.base_currency) {
        next.currency = meta.base_currency;
        changed = true;
      }

      if (next.gst_rate === "" && meta.default_gst_rate !== null && meta.default_gst_rate !== undefined) {
        next.gst_rate = String(meta.default_gst_rate);
        changed = true;
      }

      if (!next.unit) {
        const bases =
          (next.procurement_type === "goods" ? meta.goods_units : meta.service_rate_bases) || [];

        if (bases[0]) {
          next.unit = bases[0];
          changed = true;
        }
      }

      return changed ? next : prev;
    });
  }, [meta, isEdit]);

  // Seed the required-field contract. Runs only while the buyer has not touched
  // it, so unchecking every box (a legitimate "chase nothing" choice) is not
  // silently undone on the next render.
  useEffect(() => {
    if (requiredFieldsSeeded) return;

    const defaults = meta?.required_fields?.[formData.procurement_type];

    if (!defaults?.length) return;

    setRequiredFields(defaults);
    setRequiredFieldsSeeded(true);
  }, [meta, formData.procurement_type, requiredFieldsSeeded]);

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

  /**
   * Switching type re-seeds both the rate basis and the required-field contract.
   *
   * The contract is not cosmetic: it is what the completeness check measures a
   * submission against, and therefore what the follow-up engine chases. Carrying
   * a goods contract (Incoterms, MOQ) into a maintenance RFQ would have suppliers
   * chased for a shipping term on a plumbing job.
   */
  const handleProcurementTypeChange = (nextType) => {
    if (nextType === formData.procurement_type) return;

    const nextBases = (nextType === "goods" ? meta?.goods_units : meta?.service_rate_bases) || [];

    setFormData((prev) => ({
      ...prev,
      procurement_type: nextType,
      unit: nextBases[0] ?? "",
      // The two category taxonomies do not overlap, so a carried-over category
      // would be a lie about what is being bought.
      category: "",
    }));

    setRequiredFields(meta?.required_fields?.[nextType] || []);
    setRequiredFieldsSeeded(true);
    setErrors({});
  };

  const toggleRequiredField = (key) => {
    setRequiredFieldsSeeded(true);
    setRequiredFields((prev) =>
      prev.includes(key) ? prev.filter((entry) => entry !== key) : [...prev, key]
    );
  };

  const validate = () => {
    const errs = {};

    if (!formData.item_name.trim()) {
      errs.item_name = isGoods ? "Item name is required" : "Scope of works is required";
    }

    if (!formData.specification.trim()) {
      errs.specification = isGoods
        ? "Material / specification is required"
        : "Specification of works is required";
    }

    if (!formData.quantity || Number(formData.quantity) < 1) {
      errs.quantity = "Enter a valid quantity (use 1 for a lump sum)";
    }

    if (!formData.unit.trim()) {
      errs.unit = "Select a rate basis";
    }

    if (!formData.currency.trim() || formData.currency.trim().length !== 3) {
      errs.currency = "Use a 3-letter currency code";
    }

    if (!formData.delivery_expectation) {
      errs.delivery_expectation = isGoods
        ? "Delivery expectation is required"
        : "A date the works are wanted by is required";
    }

    // A deadline in the past would close the RFQ the moment it opens.
    if (formData.deadline && new Date(formData.deadline).getTime() < Date.now()) {
      errs.deadline = "Deadline must be in the future";
    }

    const gstRate = toNumber(formData.gst_rate);

    if (formData.gst_rate !== "" && (gstRate === null || gstRate < 0 || gstRate > 100)) {
      errs.gst_rate = "GST must be between 0 and 100";
    }

    if (!isGoods && formData.required_response_hours !== "") {
      const hours = toNumber(formData.required_response_hours);

      if (hours === null || hours < 0) {
        errs.required_response_hours = "Enter the response time in whole hours";
      }
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

    const text = (key) => formData[key].trim() || null;
    const gstRate = toNumber(formData.gst_rate);

    const payload = {
      item_name: formData.item_name.trim(),
      specification: formData.specification.trim(),
      quantity: Number(formData.quantity),
      unit: formData.unit.trim(),
      currency: formData.currency.trim().toUpperCase(),
      // Incoterms are goods-only; sending null for a service clears anything a
      // previous goods edit left behind.
      incoterms: isGoods ? text("incoterms") : null,
      delivery_expectation: formData.delivery_expectation,
      deadline: formData.deadline ? new Date(formData.deadline).toISOString() : null,
      category: text("category"),
      notes: text("notes"),

      // ---- services ------------------------------------------------------
      site_name: isGoods ? null : text("site_name"),
      site_address: isGoods ? null : text("site_address"),
      site_access_notes: isGoods ? null : text("site_access_notes"),
      required_response_hours: isGoods
        ? null
        : optionalInteger(formData.required_response_hours),
      required_accreditations: isGoods ? [] : formData.required_accreditations,
      // Decimal fields travel as strings: "9.00", not 9.
      gst_rate: gstRate === null ? null : gstRate.toFixed(2),

      // The contract the completeness check and the follow-up engine read.
      required_fields: requiredFields,
    };

    // `RFQCreate.procurement_type` is a plain str with a server-side default;
    // sending an explicit null would fail validation, so it is only sent when the
    // taxonomy actually gave us one.
    if (formData.procurement_type) {
      payload.procurement_type = formData.procurement_type;
    }

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
    <form onSubmit={handleSubmit} className="space-y-6">
      {metaError && (
        <p className="rounded-xl border border-warning-soft-fg/25 bg-warning-soft px-4 py-3 text-xs leading-relaxed text-warning-soft-fg">
          The procurement options could not be loaded ({metaError}), so the
          pickers below accept free text. Everything else still works.
        </p>
      )}

      {/* What is being bought -------------------------------------------------
          First, because it decides which of the two field sets below applies. */}
      <section className="space-y-3">
        <div>
          <span className="text-sm font-medium text-content">Procurement type</span>
          <p className="mt-1 text-xs text-muted">
            Services (maintenance and minor works) are scored on rate, response
            time and accreditations; goods on price, lead time and Incoterms.
          </p>
        </div>

        <div className="inline-flex rounded-xl border border-border-default bg-surface-2 p-1">
          {(meta?.procurement_types || []).map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => handleProcurementTypeChange(type)}
              aria-pressed={formData.procurement_type === type}
              className={`rounded-lg px-4 py-1.5 text-sm font-medium capitalize transition ${
                formData.procurement_type === type
                  ? "bg-surface text-content shadow-sm"
                  : "text-muted hover:text-content"
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </section>

      <FormField
        label={isGoods ? "Item Name" : "Scope of Works"}
        required
        error={errors.item_name}
      >
        <input
          name="item_name"
          type="text"
          value={formData.item_name}
          onChange={handleChange}
          placeholder={
            isGoods ? "e.g. Steel Bolt M10" : "e.g. Quarterly AHU servicing, Tower A"
          }
          className={`${inputClass} ${errors.item_name ? errorClass : ""}`}
        />
      </FormField>

      <FormField
        label={isGoods ? "Material / Specification" : "Specification of Works"}
        required
        error={errors.specification}
      >
        <input
          name="specification"
          type="text"
          value={formData.specification}
          onChange={handleChange}
          placeholder={
            isGoods
              ? "e.g. SS304, hot-rolled, 8.8 grade"
              : "e.g. Clean 12 FCUs, replace filters, test and commission"
          }
          className={`${inputClass} ${errors.specification ? errorClass : ""}`}
        />
      </FormField>

      <div className="grid gap-5 sm:grid-cols-3">
        <FormField
          label={isGoods ? "Quantity" : "Quantity / effort"}
          hint={isGoods ? undefined : "1 for a lump sum"}
          required
          error={errors.quantity}
        >
          <input
            name="quantity"
            type="number"
            min="1"
            value={formData.quantity}
            onChange={handleChange}
            placeholder={isGoods ? "e.g. 500" : "e.g. 12"}
            className={`${inputClass} ${errors.quantity ? errorClass : ""}`}
          />
        </FormField>

        <FormField
          label={isGoods ? "Unit" : "Rate basis"}
          hint={isGoods ? undefined : "what the rate is quoted against"}
          required
          error={errors.unit}
        >
          <Select
            name="unit"
            options={rateBasisOptions}
            value={formData.unit}
            onChange={handleChange}
            placeholder={isGoods ? "pcs" : "per job"}
            className={errors.unit ? errorClass : ""}
          />
        </FormField>

        <FormField
          label="Currency"
          hint="quotes are normalised to this"
          required
          error={errors.currency}
        >
          <Select
            name="currency"
            options={currencyOptions(meta?.base_currency, formData.currency)}
            value={formData.currency}
            onChange={handleChange}
            className={errors.currency ? errorClass : ""}
          />
        </FormField>
      </div>

      <div className="grid gap-5 sm:grid-cols-3">
        <FormField label="Category" hint="optional" error={errors.category}>
          <Select
            name="category"
            options={categoryOptions}
            allowEmpty
            emptyLabel="Not specified"
            value={formData.category}
            onChange={handleChange}
            placeholder={isGoods ? "e.g. Spare Parts & Consumables" : "e.g. ACMV / Air-Conditioning"}
            className={errors.category ? errorClass : ""}
          />
        </FormField>

        {isGoods && (
          <FormField label="Incoterms" hint="optional">
            <Select
              name="incoterms"
              options={INCOTERMS}
              allowEmpty
              value={formData.incoterms}
              onChange={handleChange}
            />
          </FormField>
        )}

        <FormField
          label={isGoods ? "Delivery Expectation" : "Works wanted by"}
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

        <FormField label="Quote deadline" hint="optional" error={errors.deadline}>
          <input
            name="deadline"
            type="datetime-local"
            value={formData.deadline ?? ""}
            onChange={handleChange}
            className={`${inputClass} ${errors.deadline ? errorClass : ""}`}
          />
        </FormField>
      </div>

      <div className="grid gap-5 sm:grid-cols-4">
        <FormField
          label="GST rate"
          hint="percent"
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

        <div className="sm:col-span-3 sm:self-end">
          <p className="text-xs leading-relaxed text-muted">
            Used when a supplier states a rate but no tax amount: the comparison
            derives the tax from this rate so the figure you compare is the figure
            you would be invoiced, and marks it as derived rather than quoted.
          </p>
        </div>
      </div>

      {/* Services ------------------------------------------------------------ */}
      {!isGoods && (
        <section className="space-y-5 rounded-2xl border border-border-default bg-surface-2/60 p-5">
          <div>
            <h3 className="text-sm font-semibold text-content">Site &amp; service level</h3>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              Where and when the work happens. Access hours and permit requirements
              change a contractor&apos;s price, so stating them up front is what
              makes the quotes comparable.
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <FormField label="Site name" hint="optional">
              <input
                name="site_name"
                type="text"
                value={formData.site_name}
                onChange={handleChange}
                placeholder="e.g. Tower A, Level 3"
                className={inputClass}
              />
            </FormField>

            <FormField label="Required response time" hint="hours" error={errors.required_response_hours}>
              <input
                name="required_response_hours"
                type="number"
                min="0"
                value={formData.required_response_hours}
                onChange={handleChange}
                placeholder="e.g. 4"
                className={`${inputClass} ${
                  errors.required_response_hours ? errorClass : ""
                }`}
              />
            </FormField>
          </div>

          <FormField label="Site address" hint="optional">
            <input
              name="site_address"
              type="text"
              value={formData.site_address}
              onChange={handleChange}
              placeholder="1 Marina Boulevard, Singapore 018989"
              className={inputClass}
            />
          </FormField>

          <FormField label="Site access notes" hint="optional">
            <textarea
              name="site_access_notes"
              rows={2}
              value={formData.site_access_notes}
              onChange={handleChange}
              placeholder="Access 9am-5pm weekdays. Permit-to-work required."
              className={`${inputClass} resize-none`}
            />
          </FormField>

          <FormField
            label="Required accreditations"
            hint="licences a supplier must hold"
          >
            <ChipMultiSelect
              options={meta?.common_accreditations || []}
              value={formData.required_accreditations}
              onChange={(next) => {
                setFormData((prev) => ({ ...prev, required_accreditations: next }));
                clearError("required_accreditations");
              }}
              placeholder="Add a licence or certification…"
              emptyHint="A quote missing a required accreditation has its compliance score capped, because the work may not lawfully proceed without it."
            />
          </FormField>
        </section>
      )}

      {/* Required-field contract --------------------------------------------
          This is not decoration: it is the definition of a complete quote, so it
          decides which gaps the completeness check reports and therefore what the
          follow-up engine chases. */}
      <section className="space-y-3 rounded-2xl border border-border-default bg-surface-2/60 p-5">
        <div>
          <h3 className="text-sm font-semibold text-content">Required fields</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            What a supplier must tell you for their quote to count as complete.
            Anything unticked is never chased — so this list is the difference
            between a quote you can compare and a gap the follow-up engine will
            email about.
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          {requiredFieldOptions.map((key) => (
            <label
              key={key}
              className="flex cursor-pointer items-center gap-3 rounded-xl border border-border-default bg-surface px-3 py-2 text-sm text-content transition hover:border-primary/40"
            >
              <input
                type="checkbox"
                checked={requiredFields.includes(key)}
                onChange={() => toggleRequiredField(key)}
                className="h-4 w-4 rounded border-border-strong text-primary focus:ring-ring/50"
              />
              <span>{labelFor(key)}</span>
            </label>
          ))}
        </div>

        {requiredFieldOptions.length === 0 && (
          <p className="text-xs text-subtle">
            The field contract could not be loaded; the server will apply the
            default for this procurement type.
          </p>
        )}
      </section>

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
