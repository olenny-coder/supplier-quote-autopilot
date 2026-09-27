import { useRef, useState } from "react";

import { Button, FormField, inputClass } from "@/shared/components/ui";
import { formatNumber, toNumber } from "@/shared/lib/format";

import {
  TEMPLATE_FILENAME,
  buildTemplateCsv,
  downloadTextFile,
  parsePastedRows,
} from "../csv";

/*
 * Bulk supplier upload — the body of the "Bulk upload" modal.
 *
 * Three parts, in the order a buyer needs them:
 *
 *   1. the duplicate policy, which applies to both paths below;
 *   2. a CSV file upload (the robust path) with a header-only template to
 *      download, so the column names are never a guess;
 *   3. a paste box (the convenience path) for a block of cells copied straight
 *      out of the spreadsheet — tab separated, first line is the header, parsed
 *      in the browser by `../csv`.
 *
 * Once an import has run the form is *replaced* by the result panel: the message,
 * the counts, and the rows that could not be imported with the spreadsheet row
 * number beside each one. A result is only ever set by the parent, so this
 * component renders exactly the outcome it was handed.
 *
 * This component owns its input state and nothing else: no requests and no
 * toasts. The parent (`SupplierImportModal`) calls the API and handles transport
 * failures, which keeps the panel renderable — and reviewable — on its own.
 */

/**
 * The two duplicate policies. `skip` is the default for a reason: re-uploading a
 * spreadsheet someone has added a column to is the normal case, and overwriting
 * the notes, risk rating and reference code they curated by hand would be the
 * worst possible default.
 */
const DUPLICATE_OPTIONS = [
  {
    value: "skip",
    label: "Skip suppliers already in my directory",
  },
  {
    value: "update",
    label: "Update them with the new details",
  },
];

/** The four counters, always in this order, zero or not. */
function importCounts(result) {
  return [
    { label: "Added", value: toNumber(result.created) ?? 0 },
    { label: "Updated", value: toNumber(result.updated) ?? 0 },
    { label: "Already in your directory", value: toNumber(result.skipped) ?? 0 },
    { label: "Could not be imported", value: toNumber(result.failed) ?? 0 },
  ];
}

/**
 * How the outcome reads at a glance: nothing wrong, some rows in and some out, or
 * nothing at all. Tone classes are written out in full because Tailwind scans
 * source text — a `border-${tone}` template string would generate nothing.
 */
function resultTone(created, updated, failed) {
  if (!failed) {
    return {
      headline: "Import complete",
      panel: "border-success/30 bg-success-soft text-success-soft-fg",
    };
  }

  if (created + updated > 0) {
    return {
      headline: "Import finished with problems",
      panel: "border-warning-soft-fg/30 bg-warning-soft text-warning-soft-fg",
    };
  }

  return {
    headline: "Nothing could be imported",
    panel: "border-danger/30 bg-danger-soft text-danger-soft-fg",
  };
}

function Th({ children }) {
  return (
    <th
      scope="col"
      className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-subtle"
    >
      {children}
    </th>
  );
}

function ImportResultPanel({ result, onReset, onClose }) {
  const created = toNumber(result.created) ?? 0;
  const updated = toNumber(result.updated) ?? 0;
  const failed = toNumber(result.failed) ?? 0;

  const errors = Array.isArray(result.errors) ? result.errors : [];
  const tone = resultTone(created, updated, failed);

  return (
    <div className="space-y-5">
      <div className={`rounded-xl border px-4 py-3 ${tone.panel}`}>
        <h3 className="text-sm font-semibold">{tone.headline}</h3>
        <p className="mt-1 text-sm leading-relaxed">{result.message}</p>
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {importCounts(result).map((count) => (
          <div
            key={count.label}
            className="rounded-xl border border-border-default bg-surface-2 px-3 py-2.5"
          >
            <dt className="text-xs font-medium text-muted">{count.label}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-content">
              {formatNumber(count.value)}
            </dd>
          </div>
        ))}
      </dl>

      {errors.length === 0 ? (
        <p className="text-sm text-muted">
          Every row was imported — nothing to fix.
        </p>
      ) : (
        <div>
          <h3 className="text-sm font-semibold text-content">
            Rows that could not be imported
          </h3>
          <p className="mt-1 text-xs text-muted">
            The row number is the line in your spreadsheet, counting the header
            as row 1.
          </p>

          <div className="mt-3 overflow-hidden rounded-xl border border-border-default">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-border-default bg-surface-2">
                    <Th>Row</Th>
                    <Th>Supplier</Th>
                    <Th>Email</Th>
                    <Th>Reason</Th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-border-default">
                  {errors.map((entry, index) => (
                    <tr key={`${entry.row}-${index}`}>
                      <td className="px-4 py-3 align-top font-medium tabular-nums text-content">
                        {entry.row}
                      </td>
                      <td className="px-4 py-3 align-top text-content">
                        {entry.name || "—"}
                      </td>
                      <td className="px-4 py-3 align-top text-muted">
                        {entry.email || "—"}
                      </td>
                      <td className="px-4 py-3 align-top leading-relaxed text-muted">
                        {entry.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3 pt-1 sm:flex-row sm:justify-end">
        <Button
          type="button"
          variant="outline"
          className="min-h-11"
          onClick={onReset}
        >
          Import more
        </Button>

        {onClose && (
          <Button type="button" className="min-h-11" onClick={onClose}>
            Done
          </Button>
        )}
      </div>
    </div>
  );
}

function BulkSupplierImport({
  result = null,
  isImporting = false,
  onImportFile,
  onImportPaste,
  onReset,
  onClose,
}) {
  const fileInputRef = useRef(null);

  const [onDuplicate, setOnDuplicate] = useState("skip");
  const [file, setFile] = useState(null);
  const [pasted, setPasted] = useState("");
  const [fileError, setFileError] = useState(null);
  const [pasteError, setPasteError] = useState(null);

  const handleFileChange = (event) => {
    setFile(event.target.files?.[0] ?? null);
    setFileError(null);
  };

  const handleDownloadTemplate = () => {
    downloadTextFile(TEMPLATE_FILENAME, buildTemplateCsv());
  };

  const handleFileImport = () => {
    if (!file) {
      setFileError("Choose a CSV file first.");
      return;
    }

    setFileError(null);
    onImportFile?.(file, onDuplicate);
  };

  const handlePasteImport = () => {
    if (!pasted.trim()) {
      setPasteError("Paste some rows first — the first line should be the column names.");
      return;
    }

    setPasteError(null);
    onImportPaste?.(parsePastedRows(pasted), onDuplicate);
  };

  const handleReset = () => {
    // A fresh import starts from a clean slate: the previous file and paste are
    // gone, the duplicate policy the buyer chose is kept.
    setFile(null);
    setPasted("");
    setFileError(null);
    setPasteError(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    onReset?.();
  };

  if (result) {
    return (
      <ImportResultPanel result={result} onReset={handleReset} onClose={onClose} />
    );
  }

  return (
    <div className="space-y-6">
      <fieldset>
        <legend className="text-sm font-medium text-content">
          If a supplier is already in your directory
        </legend>

        <div className="mt-2 space-y-2">
          {DUPLICATE_OPTIONS.map((option) => (
            <label
              key={option.value}
              className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-border-default bg-surface-inset px-4 py-2.5 text-sm text-content transition hover:bg-surface-hover"
            >
              <input
                type="radio"
                name="supplier-import-on-duplicate"
                value={option.value}
                checked={onDuplicate === option.value}
                onChange={(event) => setOnDuplicate(event.target.value)}
                className="h-4 w-4 shrink-0 accent-primary"
              />
              {option.label}
            </label>
          ))}
        </div>

        <p className="mt-2 text-xs leading-relaxed text-muted">
          Skipping keeps the notes, risk ratings and reference codes you have
          already set by hand. Updating overwrites them with what the file says.
        </p>
      </fieldset>

      <section className="rounded-2xl border border-border-default bg-surface p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-content">
              Upload a CSV file
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              Column names are matched loosely. A company column (Supplier,
              Company, Vendor or Name) and an email column (Email or Contact
              Email) are required; Contact Person, Phone, Website, Country, City,
              Risk and Vendor Code are used when present.
            </p>
          </div>

          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-h-11"
            onClick={handleDownloadTemplate}
          >
            Download template
          </Button>
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            ref={fileInputRef}
            id="supplier-import-file"
            type="file"
            accept=".csv,text/csv"
            onChange={handleFileChange}
            className="sr-only"
          />

          <Button
            type="button"
            variant="soft"
            className="min-h-11"
            onClick={() => fileInputRef.current?.click()}
          >
            Choose a CSV file
          </Button>

          <p className="min-w-0 text-xs text-muted">
            {file
              ? `${file.name} — ${formatNumber(Math.max(1, Math.round(file.size / 1024)))} KB`
              : "No file chosen yet."}
          </p>
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted">
            Up to 2 MB. One row per supplier.
          </p>

          <Button
            type="button"
            className="min-h-11"
            loading={isImporting}
            loadingText="Importing…"
            onClick={handleFileImport}
          >
            Import file
          </Button>
        </div>

        {fileError && (
          <p className="mt-3 text-xs text-danger">{fileError}</p>
        )}
      </section>

      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border-default" />
        <span className="text-xs font-medium uppercase tracking-wide text-subtle">
          or
        </span>
        <span className="h-px flex-1 bg-border-default" />
      </div>

      <section className="rounded-2xl border border-border-default bg-surface p-4 sm:p-5">
        <h3 className="text-sm font-semibold text-content">
          Paste rows from a spreadsheet
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Select the cells in your sheet — header row included — copy, and paste
          them here. The first line is read as the column names. This is the quick
          path; if a value contains a comma, a tab, or quotes, upload the CSV
          above instead.
        </p>

        <FormField label="Pasted rows" hint="tab or comma separated">
          <textarea
            rows={6}
            value={pasted}
            onChange={(event) => {
              setPasted(event.target.value);
              setPasteError(null);
            }}
            spellCheck={false}
            aria-label="Pasted supplier rows"
            placeholder={
              "Supplier\tEmail\tContact Person\tCountry\n" +
              "Acme Facilities\tops@acme.example\tDana Tan\tSingapore"
            }
            className={`${inputClass} font-mono`}
          />
        </FormField>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted">
            Up to 500 rows per import.
          </p>

          <Button
            type="button"
            className="min-h-11"
            loading={isImporting}
            loadingText="Importing…"
            onClick={handlePasteImport}
          >
            Import pasted rows
          </Button>
        </div>

        {pasteError && (
          <p className="mt-3 text-xs text-danger">{pasteError}</p>
        )}
      </section>
    </div>
  );
}

export default BulkSupplierImport;
