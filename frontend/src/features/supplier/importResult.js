import { toNumber } from "@/shared/lib/format";

/**
 * The `SupplierImportResponse` shape with every counter at zero — what a run that
 * never reached the server looks like (a paste with no usable row at all).
 */
export function emptyImportResult() {
  return {
    created: 0,
    updated: 0,
    skipped: 0,
    failed: 0,
    total: 0,
    errors: [],
    imported: [],
    message: "",
  };
}

/**
 * One sentence a buyer can act on, with the counts that matter first.
 *
 * The wording is `SupplierService.import_message` in
 * `backend/app/features/supplier/service.py`, repeated here because the paste
 * path can merge in row problems the server never saw and so has to rewrite the
 * sentence. Keep the two in step.
 */
export function importMessage(created, updated, skipped, failed) {
  const parts = [];

  if (created) parts.push(`${created} added`);
  if (updated) parts.push(`${updated} updated`);
  if (skipped) parts.push(`${skipped} already in your directory`);
  if (failed) parts.push(`${failed} could not be imported`);

  const summary = parts.length ? parts.join(", ") : "Nothing to import";

  if (failed && !created && !updated) {
    return `${summary}. Check the row numbers below.`;
  }

  return `${summary}.`;
}

/**
 * Fold row problems found *client-side* into the server's response.
 *
 * The paste path needs this. `POST /suppliers/import` validates the whole list in
 * one Pydantic pass, so a single pasted row with a missing name or a malformed
 * address would reject the entire batch with a 422 and import nothing — the
 * opposite of the CSV endpoint's row-by-row behaviour. So the parser rejects such
 * a row before it is sent, and the buyer sees it as one more failed row, exactly
 * like the rows the server refused. The backend merges its parse problems into
 * the import result the same way.
 *
 * With no client-side problems the server's response is returned untouched, so
 * its own `message` and `total` are what the buyer reads.
 */
export function mergeRowProblems(result, problems = []) {
  const base = result ?? emptyImportResult();

  if (!problems.length) {
    return base;
  }

  const created = toNumber(base.created) ?? 0;
  const updated = toNumber(base.updated) ?? 0;
  const skipped = toNumber(base.skipped) ?? 0;

  const errors = [
    ...problems,
    ...(Array.isArray(base.errors) ? base.errors : []),
  ];

  return {
    ...base,
    created,
    updated,
    skipped,
    errors,
    failed: errors.length,
    total: created + updated + skipped + errors.length,
    message: importMessage(created, updated, skipped, errors.length),
  };
}
