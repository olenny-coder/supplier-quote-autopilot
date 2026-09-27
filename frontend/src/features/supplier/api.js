import client from "@/shared/api/client";

/**
 * Supplier directory API.
 *
 * Thin wrappers around the buyer API's `/suppliers` endpoints. Every function
 * returns `response.data` so callers never reach into Axios internals, and the
 * shared client interceptor has already flattened backend failures into plain
 * `Error(message)` instances by the time they reject here.
 *
 * `GET /suppliers` returns `SupplierStats[]`: the supplier record plus
 * `invitations_total`, `invitations_responded`, `quotes_total` and
 * `average_response_hours`. The counts are serialised by Python and can arrive
 * as JSON strings, so pages must parse them with `Number()`/`toNumber()` before
 * formatting them.
 */
export const getSuppliers = async () => {
  const response = await client.get("/suppliers");
  return response.data;
};

/**
 * Fetch a single supplier by ID
 */
export const getSupplierById = async (supplierId) => {
  const response = await client.get(`/suppliers/${supplierId}`);
  return response.data;
};

/**
 * Create a new supplier
 */
export const createSupplier = async (payload) => {
  const response = await client.post("/suppliers", payload);
  return response.data;
};

/**
 * Update an existing supplier (partial body — only send what changed)
 */
export const updateSupplier = async (supplierId, payload) => {
  const response = await client.patch(`/suppliers/${supplierId}`, payload);
  return response.data;
};

/**
 * Delete a supplier. The endpoint answers 204 with no body, so there is no
 * payload to hand back.
 */
export const deleteSupplier = async (supplierId) => {
  const response = await client.delete(`/suppliers/${supplierId}`);
  return response.data;
};

/**
 * Bulk import suppliers from an uploaded CSV — the primary path.
 *
 * The exact request is `POST /suppliers/import/csv?on_duplicate=skip|update`,
 * multipart, with a single part named `file`. The duplicate policy is a *query
 * parameter* on this endpoint (`on_duplicate: str = "skip"` in
 * `backend/app/features/supplier/router.py`), not a form field — the file is the
 * only multipart part, which is why it is passed as `params` rather than being
 * appended to the `FormData`.
 *
 * The `Content-Type` override is load-bearing, not decoration. The shared client
 * defaults every request to `application/json`, and Axios serialises a `FormData`
 * payload to JSON when the request carries a JSON content type (axios 1.x
 * `transformRequest`). Without this line the multipart body would arrive at
 * FastAPI as a JSON object and FastAPI would answer 422 for the missing `file`
 * part. Axios still lets the browser write the real header including its
 * boundary: for a `FormData` body the xhr adapter clears the content type again
 * just before sending. Never hand-set the boundary here.
 *
 * Errors reject with the shared client's normalised `Error`. A CSV with no
 * name/email column is a 400 whose `detail` (which column to rename) is already
 * the error message verbatim.
 */
export const importSuppliersCsv = async (file, { onDuplicate = "skip" } = {}) => {
  const formData = new FormData();

  formData.append("file", file);

  const response = await client.post("/suppliers/import/csv", formData, {
    params: { on_duplicate: onDuplicate },
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
};

/**
 * Bulk import suppliers from parsed rows — the paste path.
 *
 * `POST /suppliers/import` with `{ suppliers: SupplierCreate[], on_duplicate }`.
 * Unlike the CSV endpoint the whole list is validated by Pydantic in one go, so a
 * single unusable row would reject the entire batch with a 422; the paste parser
 * in `../csv` therefore rejects such a row client-side and reports it as a row
 * problem instead of sending it.
 */
export const importSuppliersJson = async (suppliers, { onDuplicate = "skip" } = {}) => {
  const response = await client.post("/suppliers/import", {
    suppliers,
    on_duplicate: onDuplicate,
  });

  return response.data;
};
