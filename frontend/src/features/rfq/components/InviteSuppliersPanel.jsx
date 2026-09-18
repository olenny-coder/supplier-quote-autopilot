import { useMemo, useState } from "react";

import { toast } from "sonner";

import { Button, FormField, inputClass } from "@/shared/components/ui";
import { RISK_RATING_OPTIONS } from "@/shared/lib/status";

import { createSupplier } from "@/features/supplier/api";
import { useSuppliers } from "@/features/supplier/hooks";

import { createInvitations } from "../api";

const errorClass = "border-danger/60 bg-danger-soft/40";

const emptySupplierRow = {
  name: "",
  contact_email: "",
  contact_name: "",
  country: "",
  risk_rating: "low",
};

/**
 * "Invite more suppliers" panel for an existing RFQ.
 *
 * Two paths, mirroring the create form: pick from the directory (bulk invite)
 * or create a brand-new supplier and invite them in one action. Suppliers who
 * already hold an invitation — including cancelled ones, since the record
 * still exists — are filtered out so nobody gets two links to the same RFQ.
 */
function InviteSuppliersPanel({ rfqId, invitations = [], onChanged }) {
  const { suppliers, loading, error: suppliersError } = useSuppliers();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState([]);
  const [sendNow, setSendNow] = useState(true);
  const [inviting, setInviting] = useState(false);

  const [newSupplier, setNewSupplier] = useState(emptySupplierRow);
  const [newSupplierErrors, setNewSupplierErrors] = useState({});
  const [creating, setCreating] = useState(false);

  const invitedSupplierIds = useMemo(
    () => new Set(invitations.map((invitation) => invitation.supplier_id)),
    [invitations]
  );

  const availableSuppliers = useMemo(() => {
    const term = query.trim().toLowerCase();

    return suppliers
      .filter((supplier) => !invitedSupplierIds.has(supplier.id))
      .filter((supplier) =>
        term
          ? [supplier.name, supplier.contact_email, supplier.country]
              .filter(Boolean)
              .some((field) => String(field).toLowerCase().includes(term))
          : true
      );
  }, [suppliers, invitedSupplierIds, query]);

  const toggleSupplier = (supplierId) => {
    setSelectedIds((prev) =>
      prev.includes(supplierId)
        ? prev.filter((id) => id !== supplierId)
        : [...prev, supplierId]
    );
  };

  const inviteSelected = async () => {
    if (!selectedIds.length) return;

    try {
      setInviting(true);

      const created = await createInvitations(rfqId, {
        supplier_ids: selectedIds,
        send_now: sendNow,
      });

      toast.success(
        sendNow
          ? `${created.length} invitation${created.length === 1 ? "" : "s"} emailed.`
          : `${created.length} invitation${created.length === 1 ? "" : "s"} created — send them when ready.`
      );

      setSelectedIds([]);
      setOpen(false);

      onChanged?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setInviting(false);
    }
  };

  const handleCreateSupplier = async (event) => {
    event.preventDefault();

    const errs = {};

    if (!newSupplier.name.trim()) errs.name = "Supplier name is required";

    if (!newSupplier.contact_email.trim()) {
      errs.contact_email = "An email is required — the form link is sent here";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newSupplier.contact_email.trim())) {
      errs.contact_email = "Enter a valid email address";
    }

    setNewSupplierErrors(errs);

    if (Object.keys(errs).length) return;

    try {
      setCreating(true);

      const supplier = await createSupplier({
        name: newSupplier.name.trim(),
        contact_email: newSupplier.contact_email.trim(),
        contact_name: newSupplier.contact_name.trim() || null,
        country: newSupplier.country.trim() || null,
        risk_rating: newSupplier.risk_rating,
      });

      await createInvitations(rfqId, {
        supplier_ids: [supplier.id],
        send_now: sendNow,
      });

      toast.success(
        sendNow
          ? `${supplier.name} added and invited.`
          : `${supplier.name} added — invitation created but not emailed.`
      );

      setNewSupplier(emptySupplierRow);
      setNewSupplierErrors({});

      onChanged?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="rounded-2xl border border-border-default bg-surface shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-content">
            Invite more suppliers
          </h3>
          <p className="mt-0.5 text-xs text-muted">
            Each new supplier gets their own private form link.
          </p>
        </div>

        <Button
          size="sm"
          variant={open ? "outline" : "soft"}
          onClick={() => setOpen((prev) => !prev)}
        >
          {open ? "Close" : "Add suppliers"}
        </Button>
      </div>

      {open && (
        <div className="space-y-6 border-t border-border-default p-5">
          {/* Directory picker */}
          <div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h4 className="text-sm font-medium text-content">
                From your directory
              </h4>

              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search…"
                aria-label="Search suppliers"
                className="w-full rounded-lg border border-border-default bg-surface py-2 px-3 text-sm text-content placeholder:text-subtle transition focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/50 sm:w-56"
              />
            </div>

            <div className="mt-3 max-h-56 overflow-y-auto rounded-xl border border-border-default">
              {loading ? (
                <p className="px-4 py-6 text-center text-sm text-muted">
                  Loading suppliers…
                </p>
              ) : suppliersError ? (
                <p className="px-4 py-6 text-center text-sm text-danger">
                  {suppliersError}
                </p>
              ) : availableSuppliers.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-muted">
                  {suppliers.length === 0
                    ? "Your directory is empty — create a supplier below."
                    : "Every matching supplier already has an invitation."}
                </p>
              ) : (
                <ul className="divide-y divide-border-default">
                  {availableSuppliers.map((supplier) => (
                    <li key={supplier.id}>
                      <label className="flex cursor-pointer items-center gap-3 px-4 py-3 transition hover:bg-surface-hover">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(supplier.id)}
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

            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-xs text-muted">
                <input
                  type="checkbox"
                  checked={sendNow}
                  onChange={(event) => setSendNow(event.target.checked)}
                  className="h-4 w-4 rounded border-border-strong text-primary focus:ring-ring/50"
                />
                Email the links immediately
              </label>

              <Button
                size="sm"
                disabled={!selectedIds.length}
                loading={inviting}
                loadingText="Inviting…"
                onClick={inviteSelected}
              >
                Invite {selectedIds.length || ""}
              </Button>
            </div>
          </div>

          {/* New supplier */}
          <form
            onSubmit={handleCreateSupplier}
            className="space-y-4 border-t border-border-default pt-5"
          >
            <h4 className="text-sm font-medium text-content">
              Create a new supplier and invite them
            </h4>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField label="Name" required error={newSupplierErrors.name}>
                <input
                  type="text"
                  value={newSupplier.name}
                  onChange={(event) =>
                    setNewSupplier((prev) => ({ ...prev, name: event.target.value }))
                  }
                  placeholder="e.g. ABC Metals Ltd."
                  className={`${inputClass} ${
                    newSupplierErrors.name ? errorClass : ""
                  }`}
                />
              </FormField>

              <FormField
                label="Contact email"
                required
                error={newSupplierErrors.contact_email}
              >
                <input
                  type="email"
                  value={newSupplier.contact_email}
                  onChange={(event) =>
                    setNewSupplier((prev) => ({
                      ...prev,
                      contact_email: event.target.value,
                    }))
                  }
                  placeholder="sales@abcmetals.com"
                  className={`${inputClass} ${
                    newSupplierErrors.contact_email ? errorClass : ""
                  }`}
                />
              </FormField>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <FormField label="Contact name" hint="optional">
                <input
                  type="text"
                  value={newSupplier.contact_name}
                  onChange={(event) =>
                    setNewSupplier((prev) => ({
                      ...prev,
                      contact_name: event.target.value,
                    }))
                  }
                  placeholder="Priya Raman"
                  className={inputClass}
                />
              </FormField>

              <FormField label="Country" hint="optional">
                <input
                  type="text"
                  value={newSupplier.country}
                  onChange={(event) =>
                    setNewSupplier((prev) => ({
                      ...prev,
                      country: event.target.value,
                    }))
                  }
                  placeholder="India"
                  className={inputClass}
                />
              </FormField>

              <FormField label="Risk rating">
                <select
                  value={newSupplier.risk_rating}
                  onChange={(event) =>
                    setNewSupplier((prev) => ({
                      ...prev,
                      risk_rating: event.target.value,
                    }))
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

            <div className="flex justify-end">
              <Button
                type="submit"
                size="sm"
                variant="outline"
                loading={creating}
                loadingText="Saving…"
              >
                Create &amp; invite
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export default InviteSuppliersPanel;
