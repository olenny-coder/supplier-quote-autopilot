import { useState } from "react";

import { toast } from "sonner";

import Modal from "@/shared/components/Modal";
import { toNumber } from "@/shared/lib/format";

import { importSuppliersCsv, importSuppliersJson } from "../api";
import { mergeRowProblems } from "../importResult";
import BulkSupplierImport from "./BulkSupplierImport";

/*
 * "Bulk upload" modal for the supplier directory.
 *
 * Owns the two requests and the outcome; the form itself lives in
 * `BulkSupplierImport`. Two paths, one result shape:
 *
 *   - a CSV file → `POST /suppliers/import/csv` (multipart, part name `file`,
 *     `?on_duplicate=`), which is row-independent server-side;
 *   - pasted rows → parsed in the browser and sent as JSON to
 *     `POST /suppliers/import`, where the whole list is validated in one pass, so
 *     the parser's own row problems are merged into the response instead of
 *     being sent (see `mergeRowProblems`).
 *
 * A failed *request* is a toast — that is how the rest of the directory reports
 * them, and a 400 from the CSV endpoint carries the client's "rename that
 * column" instruction in `error.message` verbatim. Per-row import failures are
 * not toasts: they are the result panel's table, which is the whole point of the
 * feature.
 */
function SupplierImportModal({ isOpen, onClose, onImported }) {
  const [result, setResult] = useState(null);
  const [isImporting, setIsImporting] = useState(false);

  /**
   * Close and forget the last outcome. Re-opening a modal onto the previous
   * import's report would read as if it had just happened again.
   */
  const handleClose = () => {
    setResult(null);
    onClose?.();
  };

  const settle = (response, problems = []) => {
    const merged = mergeRowProblems(response, problems);

    setResult(merged);

    // Only a create or an update changes the directory list; a run that skipped
    // every row left it exactly as it was.
    const changed =
      (toNumber(merged.created) ?? 0) + (toNumber(merged.updated) ?? 0);

    if (changed > 0) {
      onImported?.();
    }
  };

  const handleImportFile = async (file, onDuplicate) => {
    try {
      setIsImporting(true);

      const response = await importSuppliersCsv(file, { onDuplicate });

      settle(response);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsImporting(false);
    }
  };

  const handleImportPaste = async ({ suppliers, problems }, onDuplicate) => {
    // Nothing the server would accept: report the parser's problems as the
    // outcome rather than posting an empty list, which is a 400 in its own right.
    if (!suppliers.length) {
      settle(null, problems);
      return;
    }

    try {
      setIsImporting(true);

      const response = await importSuppliersJson(suppliers, { onDuplicate });

      settle(response, problems);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Bulk upload suppliers"
      description="Add your contractors from the spreadsheet you already keep."
      maxWidth="max-w-3xl"
    >
      <BulkSupplierImport
        result={result}
        isImporting={isImporting}
        onImportFile={handleImportFile}
        onImportPaste={handleImportPaste}
        onReset={() => setResult(null)}
        onClose={handleClose}
      />
    </Modal>
  );
}

export default SupplierImportModal;
