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
