import { useMemo, useState } from "react";

import { Button, FormField, inputClass } from "@/shared/components/ui";
import { RISK_RATING_OPTIONS } from "@/shared/lib/status";

import { useSuppliers } from "@/features/supplier/hooks";

const errorClass = "border-danger/60 bg-danger-soft/40";

/**
 * The "suppliers step" of the RFQ form.
 *
 * Two ways to fill the invitation list, and both end up in the same submit
 * payload (`new_suppliers` for rows typed here, `supplier_ids` for directory
 * picks). The point of the step is the acceptance path: create an RFQ, add
 * three suppliers, and each one gets their own private, tokenised form link —
 * they never need an account.
 *
 * Keyed inline errors (`supplier.0.contact_email`) are owned by RFQForm so one
 * validation pass covers the whole form; this component only renders them.
 */
function RFQSupplierStep({
  newSuppliers,
  onNewSuppliersChange,
  selectedSupplierIds,
  onSelectedSupplierIdsChange,
  sendInvitations,
  onSendInvitationsChange,
  errors,
  onClearError,
}) {
  const { suppliers, loading, error } = useSuppliers();
  const [query, setQuery] = useState("");

  const filteredSuppliers = useMemo(() => {
    const term = query.trim().toLowerCase();

    if (!term) return suppliers;

    return suppliers.filter((supplier) =>
      [supplier.name, supplier.contact_email, supplier.country]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(term))
    );
  }, [suppliers, query]);

  const updateRow = (index, field, value) => {
    onNewSuppliersChange(
      newSuppliers.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    );
    onClearError(`supplier.${index}.${field}`);
  };

  const addRow = () => {
    onNewSuppliersChange([
      ...newSuppliers,
      { name: "", contact_email: "", contact_name: "", country: "", risk_rating: "low" },
    ]);
  };

  const removeRow = (index) => {
    onNewSuppliersChange(newSuppliers.filter((_, i) => i !== index));
  };

  const toggleSupplier = (supplierId) => {
    onSelectedSupplierIdsChange(
      selectedSupplierIds.includes(supplierId)
        ? selectedSupplierIds.filter((id) => id !== supplierId)
        : [...selectedSupplierIds, supplierId]
    );
  };

  return (
    <div className="space-y-5 rounded-2xl border border-border-default bg-surface-2/60 p-5">
      <div>
        <h3 className="text-sm font-semibold text-content">Suppliers to invite</h3>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Each supplier automatically gets their own private form link — no
          account, and no way to see the other quotes. You can add three here and
          you are done.
        </p>
      </div>

      {/* New suppliers typed inline */}
      <div className="space-y-3">
        {newSuppliers.map((row, index) => (
          <div
            key={index}
            className="rounded-xl border border-border-default bg-surface p-4"
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-subtle">
                New supplier {index + 1}
              </span>

              {newSuppliers.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeRow(index)}
                  className="rounded-lg px-2 py-1 text-xs font-medium text-subtle transition hover:bg-danger-soft hover:text-danger-soft-fg"
                >
                  Remove
                </button>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                label="Supplier name"
                required
                error={errors[`supplier.${index}.name`]}
              >
                <input
                  type="text"
                  value={row.name}
                  onChange={(event) => updateRow(index, "name", event.target.value)}
                  placeholder="e.g. ABC Metals Ltd."
                  className={`${inputClass} ${
                    errors[`supplier.${index}.name`] ? errorClass : ""
                  }`}
                />
              </FormField>

              <FormField
                label="Contact email"
                required
                error={errors[`supplier.${index}.contact_email`]}
              >
                <input
                  type="email"
                  value={row.contact_email}
                  onChange={(event) =>
                    updateRow(index, "contact_email", event.target.value)
                  }
                  placeholder="sales@abcmetals.com"
                  className={`${inputClass} ${
                    errors[`supplier.${index}.contact_email`] ? errorClass : ""
                  }`}
                />
              </FormField>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <FormField label="Contact name" hint="optional">
                <input
                  type="text"
                  value={row.contact_name}
                  onChange={(event) =>
                    updateRow(index, "contact_name", event.target.value)
                  }
                  placeholder="Priya Raman"
                  className={inputClass}
                />
              </FormField>

              <FormField label="Country" hint="optional">
                <input
                  type="text"
                  value={row.country}
                  onChange={(event) => updateRow(index, "country", event.target.value)}
                  placeholder="India"
                  className={inputClass}
                />
              </FormField>

              <FormField label="Risk rating">
                <select
                  value={row.risk_rating}
                  onChange={(event) =>
                    updateRow(index, "risk_rating", event.target.value)
                  }
                  className={inputClass}
                >
                  {RISK_RATING_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </FormField>
            </div>
          </div>
        ))}

        <Button type="button" variant="outline" size="sm" onClick={addRow}>
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
          </svg>
          Add another supplier
        </Button>
      </div>

      {/* Directory picker */}
      <div className="border-t border-border-default pt-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h4 className="text-sm font-semibold text-content">
              Or invite from your directory
            </h4>
            <p className="mt-0.5 text-xs text-muted">
              {selectedSupplierIds.length} selected
            </p>
          </div>

          <div className="relative w-full sm:w-64">
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search suppliers…"
              aria-label="Search suppliers"
              className="w-full rounded-lg border border-border-default bg-surface py-2 pl-3 pr-3 text-sm text-content placeholder:text-subtle transition focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/50"
            />
          </div>
        </div>

        <div className="mt-3 max-h-56 overflow-y-auto rounded-xl border border-border-default bg-surface">
          {loading ? (
            <p className="px-4 py-6 text-center text-sm text-muted">
              Loading suppliers…
            </p>
          ) : error ? (
            <p className="px-4 py-6 text-center text-sm text-danger">{error}</p>
          ) : filteredSuppliers.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted">
              {suppliers.length === 0
                ? "No saved suppliers yet — add one above and it will be kept in your directory."
                : "No supplier matches that search."}
            </p>
          ) : (
            <ul className="divide-y divide-border-default">
              {filteredSuppliers.map((supplier) => (
                <li key={supplier.id}>
                  <label className="flex cursor-pointer items-center gap-3 px-4 py-3 transition hover:bg-surface-hover">
                    <input
                      type="checkbox"
                      checked={selectedSupplierIds.includes(supplier.id)}
                      onChange={() => toggleSupplier(supplier.id)}
                      className="h-4 w-4 rounded border-border-strong text-primary focus:ring-ring/50"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-content">
                        {supplier.name}
                      </span>
                      <span className="block truncate text-xs text-subtle">
                        {supplier.contact_email}
                        {supplier.country ? ` · ${supplier.country}` : ""}
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border-default bg-surface px-4 py-3">
        <input
          type="checkbox"
          checked={sendInvitations}
          onChange={(event) => onSendInvitationsChange(event.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-border-strong text-primary focus:ring-ring/50"
        />
        <span>
          <span className="block text-sm font-medium text-content">
            Email the form links now
          </span>
          <span className="mt-0.5 block text-xs text-muted">
            Uncheck to create the invitations silently and send them later from
            the RFQ&apos;s Suppliers tab.
          </span>
        </span>
      </label>
    </div>
  );
}

export default RFQSupplierStep;
